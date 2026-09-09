from abc import ABC, abstractmethod
from typing import List, Optional
from backend.app.models.job import JobCreate


class BaseJobAdapter(ABC):
    """Abstract base class for all job board and ATS connectors."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the job source, e.g. 'greenhouse', 'lever', 'indeed'."""
        pass

    @abstractmethod
    async def fetch_jobs(
        self,
        keywords: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[JobCreate]:
        """Fetch raw postings from source and return normalized JobCreate schemas."""
        pass
