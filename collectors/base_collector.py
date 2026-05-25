import asyncio
import aiohttp
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseCollector(ABC):
    def __init__(self, name: str, queue: asyncio.Queue):
        self.name = name
        self.queue = queue
        self.failure_count = 0
        self.max_failures = 5
        self.backoff_base = 2

    async def fetch(self, url: str, params: dict = None) -> dict:
        backoff = 1
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "User-Agent": "TradingAI/1.0 contact@example.com",
                        "Accept": "application/json"
                    }
                    async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            self.failure_count = 0
                            return await response.json()
                        elif response.status == 429:
                            logger.warning(f"{self.name}: Rate limit, {backoff}s bekleniyor")
                            await asyncio.sleep(backoff)
                            backoff *= self.backoff_base
                        else:
                            logger.error(f"{self.name}: HTTP {response.status}")
                            return {}
            except Exception as e:
                logger.error(f"{self.name}: Hata - {e}")
                await asyncio.sleep(backoff)
                backoff *= self.backoff_base

        self.failure_count += 1
        if self.failure_count >= self.max_failures:
            logger.critical(f"{self.name}: Circuit breaker devreye girdi!")
        return {}

    async def fetch_xml(self, url: str) -> dict:
        backoff = 1
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "User-Agent": "TradingAI/1.0 contact@example.com",
                        "Accept": "application/xml"
                    }
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            self.failure_count = 0
                            text = await response.text()
                            root = ET.fromstring(text)
                            items = []
                            for item in root.iter("item"):
                                items.append({
                                    "title": item.findtext("title", ""),
                                    "link": item.findtext("link", ""),
                                    "description": item.findtext("description", ""),
                                    "pubDate": item.findtext("pubDate", ""),
                                })
                            return {"items": items}
                        else:
                            logger.error(f"{self.name}: HTTP {response.status}")
                            return {}
            except Exception as e:
                logger.error(f"{self.name}: XML fetch hatası - {e}")
                await asyncio.sleep(backoff)
                backoff *= self.backoff_base

        self.failure_count += 1
        if self.failure_count >= self.max_failures:
            logger.critical(f"{self.name}: Circuit breaker devreye girdi!")
        return {}

    async def fetch_post(self, url: str, payload: dict) -> dict:
        backoff = 1
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "User-Agent": "TradingAI/1.0 contact@example.com",
                        "Content-Type": "application/json"
                    }
                    async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            self.failure_count = 0
                            return await response.json()
                        else:
                            logger.error(f"{self.name}: HTTP {response.status}")
                            return {}
            except Exception as e:
                logger.error(f"{self.name}: POST hatası - {e}")
                await asyncio.sleep(backoff)
                backoff *= self.backoff_base

        self.failure_count += 1
        if self.failure_count >= self.max_failures:
            logger.critical(f"{self.name}: Circuit breaker devreye girdi!")
        return {}

    @abstractmethod
    async def collect(self):
        pass

    async def run(self, interval_seconds: int = 300):
        logger.info(f"{self.name} başladı")
        while True:
            try:
                if self.failure_count < self.max_failures:
                    await self.collect()
                else:
                    logger.warning(f"{self.name}: Circuit breaker açık, bekleniyor...")
                    await asyncio.sleep(60)
                    self.failure_count = 0
            except Exception as e:
                logger.error(f"{self.name}: Run hatası - {e}")
            await asyncio.sleep(interval_seconds)