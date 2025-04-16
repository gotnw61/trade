# -*- coding: utf-8 -*-
import asyncio
import queue
import threading
from loguru import logger

class PriceQueue:
    """
    Thread-safe price queue that can be used from both async and sync contexts
    """
    def __init__(self, loop=None):
        """
        Initialize the price queue
        
        Args:
            loop (asyncio.AbstractEventLoop, optional): Event loop for async operations
        """
        self._async_queue = asyncio.Queue()
        self._sync_queue = queue.Queue()
        self._loop = loop or asyncio.get_event_loop()
        
    async def put(self, item):
        """
        Asynchronously put an item in both queues
        
        Args:
            item: Item to put in the queue (e.g., (mint_address, price))
        """
        await self._async_queue.put(item)
        self._sync_queue.put(item)
        logger.debug(f"Kuyruğa eklendi: {item}")
    
    def put_async(self, item):
        """
        Thread-safe way to put an item from a sync context
        
        Args:
            item: Item to put in the queue
        """
        asyncio.run_coroutine_threadsafe(
            self._async_queue.put(item), 
            self._loop
        )
        self._sync_queue.put(item)
    
    async def get_async(self):
        """
        Asynchronously get an item from the async queue
        
        Returns:
            The next item from the queue
        """
        item = await self._async_queue.get()
        logger.debug(f"Kuyruktan alındı (async): {item}")
        return item
    
    def get_sync(self, block=True, timeout=None):
        """
        Synchronously get an item from the sync queue
        
        Args:
            block (bool): Whether to block until an item is available
            timeout (float): Timeout for blocking
            
        Returns:
            The next item from the queue or None if empty and not blocking
        """
        try:
            item = self._sync_queue.get(block=block, timeout=timeout)
            logger.debug(f"Kuyruktan alındı (sync): {item}")
            return item
        except queue.Empty:
            return None
    
    def empty(self):
        """
        Check if the queue is empty
        
        Returns:
            bool: True if the async queue is empty
        """
        return self._async_queue.empty()