#!/usr/bin/env python3
"""Test face_recognition library installation"""

import sys

try:
    import face_recognition
    print("✓ face_recognition imported")
    
    import dlib
    print(f"✓ dlib version: {dlib.__version__}")
    
    import cv2
    print(f"✓ opencv version: {cv2.__version__}")
    
    import numpy as np
    print(f"✓ numpy version: {np.__version__}")
    
    print("\n✅ All dependencies OK!")
    sys.exit(0)
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
