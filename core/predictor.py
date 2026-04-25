import os
import sys

# Suppress TensorFlow output for windowed mode
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TF warnings
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.applications.resnet50 import preprocess_input
from PIL import Image
import cv2
import logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class Predictor:
    def __init__(self, model_path):
        self.model = load_model(model_path)

    def preprocess(self, image_path):
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            return "Error: Image not found"

        # 2. Handle 16-bit normalization if necessary
        if img.dtype != np.uint8:
            img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # 3. Convert BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # 4. Resize to 80x80
        img = cv2.resize(img, (80, 80), interpolation=cv2.INTER_AREA)

        # 5. Apply ResNet50 preprocessing and add batch dimension
        img_array = np.expand_dims(img.astype('float32'), axis=0)  # Shape: (1, 80, 80, 3)
        img_array = preprocess_input(img_array)  # Scales to [-1, 1] as ResNet50 expects

        # # 6. Prediction
        # prediction = model.predict(img_array)
        # img = Image.open(image_path).convert("RGB")
        # img = img.resize((80, 80))  # ⚠️ change to your training size
        # img_array = np.array(img, dtype="float32")
        # img_array = img_array / 255.0          
        # img_array = np.expand_dims(img_array, axis=0)
        return img_array

    def predict(self, image_path):
        processed = self.preprocess(image_path)
        
        # Get raw prediction (sigmoid output → probability between 0 and 1)
        prediction = self.model.predict(processed, verbose=0)
        
        # For binary model with sigmoid: prediction shape is (1, 1)
        prob = prediction[0][0]          # Extract the probability
        
        logging.info(f"Raw probability: {prob:.4f}")
        if prob > 0.5:
            return "Pathologique", prob
        else:
            return "Non Pathologique", prob