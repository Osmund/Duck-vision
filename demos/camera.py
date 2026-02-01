#!/usr/bin/env python3
"""
Duck-Vision Camera Interface
Håndterer Pi AI Camera med picamera2
"""

import time
import numpy as np
from picamera2 import Picamera2
from PIL import Image
from config import CAMERA_CONFIG


class DuckCamera:
    """Kamerainterface for Pi AI Camera"""
    
    def __init__(self):
        self.camera = None
        self.is_running = False
        
    def start(self) -> bool:
        """Start kamera"""
        try:
            print("Starter Pi AI Camera...")
            self.camera = Picamera2()
            
            # Konfigurer kamera
            config = self.camera.create_preview_configuration(
                main={
                    "size": (CAMERA_CONFIG["width"], CAMERA_CONFIG["height"]),
                    "format": "RGB888"
                }
            )
            self.camera.configure(config)
            
            # Start kamera
            self.camera.start()
            self.is_running = True
            
            # Vent litt for at kamera skal stabilisere seg
            time.sleep(2)
            
            print(f"✓ Kamera startet: {CAMERA_CONFIG['width']}x{CAMERA_CONFIG['height']}")
            return True
            
        except Exception as e:
            print(f"❌ Kunne ikke starte kamera: {e}")
            return False
    
    def stop(self):
        """Stopp kamera"""
        if self.camera and self.is_running:
            self.camera.stop()
            self.is_running = False
            print("Kamera stoppet")
    
    def capture_array(self) -> np.ndarray:
        """Ta bilde som numpy array (RGB)"""
        if not self.is_running:
            raise RuntimeError("Kamera er ikke startet")
        
        return self.camera.capture_array()
    
    def capture_pil(self) -> Image.Image:
        """Ta bilde som PIL Image"""
        array = self.capture_array()
        return Image.fromarray(array)
    
    def save_image(self, filepath: str):
        """Ta bilde og lagre til fil"""
        image = self.capture_pil()
        image.save(filepath)
        print(f"✓ Bilde lagret: {filepath}")
    
    def __enter__(self):
        """Context manager support"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.stop()


# Test funksjon
if __name__ == "__main__":
    print("Testing Duck-Vision Camera...")
    
    with DuckCamera() as camera:
        print("\n✓ Kamera fungerer!")
        
        # Ta testbilde
        print("\nTar testbilde...")
        camera.save_image("test_image.jpg")
        
        # Ta flere bilder for å teste ytelse
        print("\nTester capture hastighet...")
        times = []
        for i in range(10):
            start = time.time()
            frame = camera.capture_array()
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  Frame {i+1}: {elapsed*1000:.1f}ms, shape: {frame.shape}")
        
        avg_time = sum(times) / len(times)
        fps = 1.0 / avg_time
        print(f"\n✓ Gjennomsnittlig FPS: {fps:.1f}")
