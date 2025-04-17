# -*- coding: utf-8 -*-
import asyncio
import sys

def run_async(coroutine, callback=None, root=None):
    """
    Asenkron bir coroutine'i çalıştırır
    
    Args:
        coroutine: Çalıştırılacak coroutine
        callback: Sonuç için geri çağırma fonksiyonu
        root: Tkinter root nesnesi (isteğe bağlı, callback için gerekli)
    """
    def _callback_wrapper(future):
        """Future'ın sonucunu alıp callback'e gönderir"""
        try:
            result = future.result()
            if callback and root and root.winfo_exists():
                root.after(0, lambda: callback(result))
        except Exception as e:
            print(f"Async çalıştırma hatası (callback): {e}")
            if callback and root and root.winfo_exists():
                root.after(0, lambda: callback(None))
    
    try:
        # Mevcut event loop'u kullan
        loop = asyncio.get_event_loop()
        
        # Burada Future oluşturuyoruz, task değil
        future = asyncio.ensure_future(coroutine)
        
        # Callback ekle
        if callback:
            future.add_done_callback(_callback_wrapper)
            
        return future
    except Exception as e:
        print(f"Async çalıştırma hatası (genel): {e}")
        import traceback
        traceback.print_exc()
        return None

async def async_input(prompt):
    """
    Asenkron olarak kullanıcıdan girdi alır.
    
    Args:
        prompt (str): Gösterilecek istem
        
    Returns:
        str: Kullanıcı girdisi
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)