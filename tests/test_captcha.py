import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from ObjDict import ObjDict
from fucker import Fucker, CaptchaAbort, CaptchaException


class CaptchaRetryTest(unittest.TestCase):
    def setUp(self):
        self.fucker = Fucker(proxies={})
        self.fucker.captcha_timeout = 1
        self.fucker.captcha_retry_interval = 0.01
        self.fucker._notify_captcha = Mock()
        self.fucker._notify_captcha_success = Mock()
        self.fucker._notify_captcha_exit = Mock()

    def test_retries_until_success(self):
        calls = {"n": 0}

        def func():
            calls["n"] += 1
            if calls["n"] < 3:
                raise CaptchaException("test")
            return "ok"

        with patch("fucker.time.sleep", return_value=None):
            result = self.fucker._run_with_captcha(func, {"course_name": "x"})
        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(self.fucker._notify_captcha.call_count, 1)
        self.assertEqual(self.fucker._notify_captcha_success.call_count, 1)

    def test_timeout_aborts(self):
        self.fucker.captcha_timeout = 0

        def func():
            raise CaptchaException("test")

        with patch("fucker.time.sleep", return_value=None):
            with self.assertRaises(CaptchaAbort):
                self.fucker._run_with_captcha(func)
        self.assertEqual(self.fucker._notify_captcha_exit.call_count, 1)

    def test_prepare_before_retry(self):
        calls = {"prepared": 0, "n": 0}

        def func():
            calls["n"] += 1
            if calls["n"] < 2:
                raise CaptchaException("test")
            return "ok"

        def prepare():
            calls["prepared"] += 1

        with patch("fucker.time.sleep", return_value=None):
            self.fucker._run_with_captcha(func, prepare=prepare)
        self.assertEqual(calls["prepared"], 1)

    def test_zhidao_query_raises_on_minus_12_even_without_ok_code(self):
        self.fucker._apiQuery = Mock(return_value=ObjDict({"code": -12}))
        with self.assertRaises(CaptchaException):
            self.fucker.zhidaoQuery("https://example.test/api", {}, encrypt=False, ok_code=None)

    def test_zhidao_query_returns_zero(self):
        self.fucker._apiQuery = Mock(return_value=ObjDict({"code": 0, "data": {}}))
        ret = self.fucker.zhidaoQuery("https://example.test/api", {}, encrypt=False, ok_code=0)
        self.assertEqual(ret.code, 0)

    def test_notify_captcha_writes_pending_and_shows_toast(self):
        fucker = Fucker(proxies={})  # setUp mocks the method on self.fucker
        with tempfile.TemporaryDirectory() as tmp:
            pending = os.path.join(tmp, "captcha_pending.json")
            fucker._captcha_pending_path = lambda: pending
            with patch("fucker.showToast") as toast:
                fucker._notify_captcha(
                    CaptchaException("code -12"),
                    {"course_name": "形势与政策", "video_name": "第1节",
                     "url": "https://example.test/course"},
                )
            self.assertTrue(fucker.captcha_pending)
            self.assertTrue(os.path.isfile(pending))
            toast.assert_called_once()
            fucker._clear_captcha_pending()
            self.assertFalse(os.path.exists(pending))


class FakeHabitFucker(Fucker):
    def __init__(self):
        super().__init__(proxies={})
        self.reports = []
        self.end_thre = 0.91
        self.speed = 1
        self.progressbar_view = False
        self.tree_view = False
        self.context = ObjDict(default=None)
        video = ObjDict({
            "videoId": "v1", "name": "测试视频", "videoSec": 100,
            "studyTotalTime": 100, "watchState": 1,
            "lessonId": 1, "id": 2, "chapterId": 3,
        })
        self.ctx = ObjDict({
            "course": ObjDict({"courseInfo": ObjDict({"name": "形策"})}),
            "chapters": ObjDict(),
            "videos": ObjDict({"v1": video}),
            "fucked_time": 0,
        }, default={})
        self.context["course"] = self.ctx

    def _checkCookies(self):
        pass

    def _checkTimeLimit(self, cid):
        pass

    def getZhidaoContext(self, RAC_id, force=False):
        return self.ctx

    def _sessionReady(self, ctx=None):
        pass

    def prelearningNote(self, RAC_id, video_id):
        return ObjDict({"studiedLessonDto": ObjDict({"id": 1})})

    def threeDimensionalCourseWare(self, video_id):
        return ObjDict()

    def watchVideo(self, video_id):
        pass

    def loadVideoPointerInfo(self, RAC_id, video_id):
        return ObjDict(default=None)

    def saveDatabaseIntervalTimeV2(self, RAC_id, video_id, played_time,
                                   last_submit, watch_point, token_id=None):
        self.reports.append((played_time, last_submit, watch_point))
        return ObjDict({"code": 0})


class FakeHabitState:
    def __init__(self, target_seconds=3):
        self.target_seconds = target_seconds
        self.target_sessions = 5
        self.minutes = 1
        self.seconds = 0
        self.completed = 0

    def remaining_seconds(self):
        return max(0, self.target_seconds - self.seconds)

    def today_seconds(self):
        return self.seconds

    def add_seconds(self, seconds):
        self.seconds += int(seconds)

    def mark_today_complete(self):
        self.completed += 1
        return True

    def completed_sessions(self):
        return self.completed


class ZhidaoRewatchTest(unittest.TestCase):
    def test_fuck_habit_completes_target(self):
        fucker = FakeHabitFucker()
        state = FakeHabitState(target_seconds=3)
        with patch("fucker.time.sleep", return_value=None), \
             patch("fucker.random", return_value=1.0), \
             patch("fucker.showToast"):
            fucker.fuckHabit("course", state, minutes=1)
        self.assertEqual(state.today_seconds(), 3)
        self.assertEqual(state.completed_sessions(), 1)

    def test_force_rewatch_plays_max_seconds(self):
        fucker = FakeHabitFucker()
        with patch("fucker.time.sleep", return_value=None), \
             patch("fucker.random", return_value=1.0), \
             patch("fucker.showToast"):
            played = fucker.fuckZhidaoVideo(
                "course", "v1", force=True, max_seconds=3,
                captcha_context={"course_name": "形策", "video_name": "测试视频"},
            )
        self.assertEqual(played, 3)
        self.assertEqual(fucker.ctx.fucked_time, 3)
        self.assertEqual(fucker.ctx.videos["v1"]["studyTotalTime"], 103)
        self.assertGreaterEqual(len(fucker.reports), 1)

    def test_already_watched_is_skipped_without_force(self):
        fucker = FakeHabitFucker()
        with patch("fucker.time.sleep", return_value=None), patch("fucker.showToast"):
            played = fucker.fuckZhidaoVideo("course", "v1")
        self.assertEqual(played, 0)
        self.assertEqual(fucker.ctx.fucked_time, 0)


if __name__ == "__main__":
    unittest.main()
