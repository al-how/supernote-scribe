import sys
import types

from app.config import Settings


def test_scheduler_job_registered_when_enabled():
    from app import worker

    jobs = []

    class FakeScheduler:
        def add_job(self, func, trigger, **kwargs):
            jobs.append((func, trigger, kwargs))

    settings = Settings(schedule_enabled=True, schedule_cron="5 4 * * *")

    result = worker.configure_scheduler(
        settings,
        scheduler=FakeScheduler(),
        wake_worker=lambda: None,
    )

    assert result is True
    assert len(jobs) == 1
    assert jobs[0][1] == "cron"
    assert jobs[0][2]["minute"] == "5"
    assert jobs[0][2]["hour"] == "4"


def test_scheduler_job_not_registered_when_disabled():
    from app import worker

    jobs = []

    class FakeScheduler:
        def add_job(self, func, trigger, **kwargs):
            jobs.append((func, trigger, kwargs))

    result = worker.configure_scheduler(
        Settings(schedule_enabled=False),
        scheduler=FakeScheduler(),
        wake_worker=lambda: None,
    )

    assert result is False
    assert jobs == []


def test_started_scheduler_wakes_worker_without_second_scan(monkeypatch):
    from app import worker

    wake_requests = []

    class FakeBackgroundScheduler:
        pass

    fake_background_module = types.ModuleType("apscheduler.schedulers.background")
    fake_background_module.BackgroundScheduler = FakeBackgroundScheduler
    monkeypatch.setitem(sys.modules, "apscheduler", types.ModuleType("apscheduler"))
    monkeypatch.setitem(sys.modules, "apscheduler.schedulers", types.ModuleType("apscheduler.schedulers"))
    monkeypatch.setitem(sys.modules, "apscheduler.schedulers.background", fake_background_module)

    def fake_configure_scheduler(settings, *, scheduler, wake_worker):
        wake_worker()
        return False

    monkeypatch.setattr(worker, "configure_scheduler", fake_configure_scheduler)
    monkeypatch.setattr(
        worker,
        "_wake_processing_loop_threadsafe",
        lambda *, scan_before_process=False: wake_requests.append(scan_before_process),
    )

    worker.worker_state.scheduler = None
    worker.start_watcher_and_scheduler(Settings(schedule_enabled=True, watch_enabled=False))

    assert wake_requests == [False]
