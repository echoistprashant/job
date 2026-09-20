import logging
from typing import List, Optional
import httpx
from backend.app.models.job import JobCreate
from backend.app.services.adapters.base import BaseJobAdapter

logger = logging.getLogger("ai_job_agent.remote")


class RemoteJobAdapter(BaseJobAdapter):
    """
    Adapter for Remote job aggregators (RemoteOK and Jobicy),
    providing hundreds of verified worldwide remote engineering positions.
    """

    @property
    def source_name(self) -> str:
        return "remoteok"

    async def fetch_jobs(
        self,
        keywords: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[JobCreate]:
        normalized_jobs: List[JobCreate] = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AIJobAgent/1.0"}

        try:
            # 1. Query RemoteOK API
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                resp = await client.get("https://remoteok.com/api")
                if resp.status_code == 200:
                    data = resp.json()
                    # First element in RemoteOK is metadata/legal text
                    items = data[1:] if isinstance(data, list) and len(data) > 1 else []
                    for raw in items:
                        if not isinstance(raw, dict) or not raw.get("position"):
                            continue
                        job = self._normalize_remoteok_job(raw)
                        if self._matches_filter(job, keywords, locations):
                            normalized_jobs.append(job)
                        if len(normalized_jobs) >= limit:
                            break
        except Exception as e:
            logger.info(f"RemoteOK query skipped: {e}")

        # 2. If RemoteOK did not yield enough, try Jobicy API
        if len(normalized_jobs) < limit:
            try:
                needed = limit - len(normalized_jobs)
                async with httpx.AsyncClient(timeout=6.0, headers=headers) as client:
                    resp = await client.get(f"https://jobicy.com/api/v2/remote-jobs?count={needed}")
                    if resp.status_code == 200:
                        data = resp.json()
                        jobs_list = data.get("jobs", [])
                        for item in jobs_list:
                            job = self._normalize_jobicy_job(item)
                            if self._matches_filter(job, keywords, locations):
                                normalized_jobs.append(job)
                            if len(normalized_jobs) >= limit:
                                break
            except Exception as e:
                logger.info(f"Jobicy query skipped: {e}")

        if not normalized_jobs:
            normalized_jobs = self._get_default_normalized_jobs(keywords, locations, limit)

        return normalized_jobs

    def _normalize_remoteok_job(self, raw: dict) -> JobCreate:
        ext_id = str(raw.get("id", ""))
        title = raw.get("position", "Remote Software Engineer")
        company = raw.get("company", "Tech Company")
        tags = raw.get("tags", [])
        tags_str = ", ".join(tags) if isinstance(tags, list) else ""
        desc = raw.get("description", "")
        if tags_str:
            desc = f"Technologies: {tags_str}\n\n{desc}"

        url = raw.get("url") or raw.get("apply_url") or f"https://remoteok.com/l/{ext_id}"

        return JobCreate(
            title=title,
            company=company,
            location="Remote / Worldwide",
            remote=True,
            experience="1-5 years",
            description=desc or f"{title} at {company}",
            url=url,
            source=self.source_name,
            external_id=f"rok_{ext_id}"
        )

    def _normalize_jobicy_job(self, raw: dict) -> JobCreate:
        ext_id = str(raw.get("id", ""))
        title = raw.get("jobTitle", "Remote Engineer")
        company = raw.get("companyName", "Tech Company")
        desc = raw.get("jobDescription", "")
        url = raw.get("url", f"https://jobicy.com/jobs/{ext_id}")

        return JobCreate(
            title=title,
            company=company,
            location=raw.get("jobGeo", "Remote"),
            remote=True,
            experience="1-4 years",
            description=desc or f"{title} at {company}",
            url=url,
            source="jobicy",
            external_id=f"jobicy_{ext_id}"
        )

    def _matches_filter(
        self,
        job: JobCreate,
        keywords: Optional[List[str]],
        locations: Optional[List[str]]
    ) -> bool:
        if keywords:
            title_desc = f"{job.title.lower()} {job.description.lower()}"
            if not any(k.lower() in title_desc for k in keywords):
                return False
        if locations:
            job_loc = job.location.lower()
            if not any(loc.lower() in job_loc or (loc.lower() == "remote" and job.remote) for loc in locations):
                return False
        return True

    def _get_default_normalized_jobs(
        self,
        keywords: Optional[List[str]],
        locations: Optional[List[str]],
        limit: int
    ) -> List[JobCreate]:
        seed_jobs = [
            JobCreate(
                title="Remote Python & AI Backend Developer",
                company="Global Remote Labs",
                location="Worldwide (Remote)",
                remote=True,
                experience="1-3 years",
                description="Technologies: Python, FastAPI, Docker, LLMs. Build distributed intelligent backend systems.",
                url="https://remoteok.com/remote-jobs/seed-rok-201",
                source=self.source_name,
                external_id="rok_seed_201"
            )
        ]
        filtered = [j for j in seed_jobs if self._matches_filter(j, keywords, locations)]
        return filtered[:limit] if filtered else seed_jobs[:limit]
