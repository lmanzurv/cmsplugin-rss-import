# -*- coding: utf-8 -*-
from apscheduler.jobstores.base import BaseJobStore, ConflictingIdError, JobLookupError
from .models import DjangoJob

class DjangoJobStore(BaseJobStore):

    """
    Stores jobs in a Django database.
    """

    def lookup_job(self, job_id):
        try:
            job_state = DjangoJob.objects.only('job_state').get(job_id=job_id).job_state
        except:
            job_state = None
        return self._reconstitute_job(job_state) if job_state else None

    def get_due_jobs(self, now):
        return self._get_jobs(next_run_time__lte=now)

    def get_next_run_time(self):
        try:
            return DjangoJob.objects.only('next_run_time').filter(next_run_time__isnull=False).order_by('next_run_time').first().next_run_time
        except AttributeError:  # no active jobs
            return None

    def get_all_jobs(self):
        jobs = self._get_jobs()
        self._fix_paused_jobs_sorting(jobs)
        return jobs

    def add_job(self, job):
        try:
            DjangoJob.objects.create(
                job_id=job.id,
                next_run_time=job.next_run_time,
                job_state=job.__getstate__()
            )
        except:
            raise ConflictingIdError(job.id)

    def update_job(self, job):
        DjangoJob.objects.filter(job_id=job.id).update(
            next_run_time=job.next_run_time,
            job_state=job.__getstate__()
        )

    def remove_job(self, job_id):
        deleted, _ = DjangoJob.objects.filter(job_id=job_id).delete()
        if deleted == 0:
            raise JobLookupError(job_id)

    def remove_all_jobs(self):
        DjangoJob.objects.delete()

    def _reconstitute_job(self, job_state):
        from apscheduler.job import Job
        job_state['jobstore'] = self
        job = Job.__new__(Job)
        job.__setstate__(job_state)
        job._scheduler = self._scheduler
        job._jobstore_alias = self._alias
        return job

    def _get_jobs(self, **filters):
        job_states = DjangoJob.objects.filter(**filters).values_list('job_id', 'job_state')
        jobs = []
        failed_job_ids = set()
        for job_id, job_state in job_states:
            try:
                jobs.append(self._reconstitute_job(job_state))
            except:
                self._logger.exception('Unable to restore job "%s" -- removing it', job_id)
                failed_job_ids.add(job_id)

        # Remove all the jobs we failed to restore
        DjangoJob.objects.filter(job_id__in=failed_job_ids).delete()

        return jobs
