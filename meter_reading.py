# meter_reading.py
import cv2
import numpy as np
import tensorflow as tf
import logging
import argparse
import requests
import os
import sys
import json
import ast

# Set up logging for better output control
logging.basicConfig(level=logging.INFO)

class MeterReader:
    def __init__(self, model_path):
        """
        Initialize the MeterReader with a TensorFlow Lite model.
        
        Args:
            model_path (str): Path to the TensorFlow Lite model file.
        """
        # Load the TensorFlow Lite model
        self.interpreter = tf.lite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()

        # Get input and output details
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        # Get input shape for preprocessing
        self.input_shape = self.input_details[0]['shape'][1:3]

    def preprocess_image(self, image):
        """
        Preprocess the image for the TensorFlow Lite model.
        
        Args:
            image (numpy.ndarray): Input image (RGB format).
        
        Returns:
            numpy.ndarray: Preprocessed image (normalized, resized).
        """
        if image is None or image.size == 0:
            raise ValueError("Invalid or empty image provided for preprocessing.")

        # Resize the image to the model's input size
        image = cv2.resize(image, (self.input_shape[1], self.input_shape[0]))

        # Normalize the image to [0, 1] (uncomment if required by the model)
        # image = image / 255.0

        # Add batch dimension
        image = np.expand_dims(image, axis=0).astype(np.float32)

        return image

    def predict(self, image):
        """
        Predict the meter reading from the input image.
        
        Args:
            image (numpy.ndarray): Input image (RGB format).
        
        Returns:
            float: Predicted meter reading.
        """
        # Preprocess the image
        input_image = self.preprocess_image(image)

        # Set the input tensor
        self.interpreter.set_tensor(self.input_details[0]['index'], input_image)

        # Run inference
        self.interpreter.invoke()

        # Get the output tensor
        output = self.interpreter.get_tensor(self.output_details[0]['index'])

        # Extract the predicted meter reading
        # Using argmax to handle classification output (e.g., 10 classes for digits 0-9)
        meter_reading = np.argmax(output[0]) / 10

        return meter_reading

    def visualize(self, image, regions, meter_readings, raw=True):
        """
        Visualize the meter readings on the image.
        
        Args:
            image (numpy.ndarray): Input image (BGR format).
            regions (list): List of tuples defining the regions (x1, y1, x2, y2).
            meter_readings (list): Predicted meter readings for each region.
            raw (bool): If True, display raw readings; otherwise, display processed readings.
        
        Returns:
            numpy.ndarray: Image with the meter readings displayed.
        """
        # Add the meter readings as text on each region
        for region, reading in zip(regions, meter_readings):
            x1, y1, x2, y2 = region
            if raw:
                # Display raw readings (floats)
                cv2.putText(image, f"{reading:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            else:
                # Display processed readings (integers)
                cv2.putText(image, f"{int(round(reading))}", (x1 + 10, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            # Draw a rectangle around the region
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

        return image


def load_regions(regions_source):
    """
    Load regions from a file or a list of coordinates.
    
    Args:
        regions_source (str): Path to the JSON file or a string representation of a list of regions.
        
    Returns:
        list: List of tuples defining the regions (x1, y1, x2, y2).
    """
    try:
        # Check if the input is a file
        if os.path.exists(regions_source):
            with open(regions_source, "r") as f:
                regions = json.load(f)
        else:
            # Assume the input is a string representation of a list
            # Remove any outer quotes and parse the list
            regions_source = regions_source.strip().strip('"').strip("'")
            regions = ast.literal_eval(regions_source)
        
        # Ensure each region has 4 values (x1, y1, x2, y2)
        return [tuple(region) for region in regions if len(region) == 4]
    except (FileNotFoundError, json.JSONDecodeError, SyntaxError, ValueError) as e:
        logging.error(f"Error loading regions: {e}")
        return []


def load_image(image_source):
    """
    Load an image from a local file or a remote URL.
    
    Args:
        image_source (str): Path to the local image file or URL of the remote image.
        
    Returns:
        numpy.ndarray: Image in OpenCV format, or None if loading fails.
    """
    if image_source.startswith(('http://', 'https://')):
        # Load image from a remote URL
        try:
            response = requests.get(image_source)
            response.raise_for_status()  # Raise an error for bad responses (e.g., 404)
            image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            return image
        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading image from {image_source}: {e}")
            return None
    else:
        # Load image from a local file
        if not os.path.exists(image_source):
            logging.error(f"Local image file {image_source} not found.")
            return None
        image = cv2.imread(image_source)
        if image is None:
            logging.error(f"Unable to load image from {image_source}.")
        return image


def validate_args(args):
    """
    Validate the command-line arguments.
    
    Args:
        args: Parsed command-line arguments.
        
    Returns:
        bool: True if all arguments are valid, False otherwise.
    """
    if not os.path.exists(args.model):
        logging.error(f"Model file {args.model} not found.")
        return False

    if not args.regions:
        logging.error("No regions provided.")
        return False

    return True


def print_help():
    """
    Print help information for the script.
    """
    print("Usage: python meter_reading.py --model MODEL_PATH --regions REGIONS_SOURCE --image_source IMAGE_SOURCE [--no-gui] [--no-output-image]")
    print("\nArguments:")
    print("  --model          Path to the TensorFlow Lite model file.")
    print("  --regions        Path to the JSON file or a string representation of a list of regions (e.g., \"[[x1,y1,x2,y2], [x1,y1,x2,y2]]\").")
    print("  --image_source   Path to the local image file or URL of the remote image.")
    print("  --no-gui         Disable GUI (no image display).")
    print("  --no-output-image Do not save the output image with annotations.")
    print("\nExample:")
    print("  python meter_reading.py --model model.tflite --regions regions.json --image_source http://192.168.1.113/img_tmp/alg.jpg")
    print("  python meter_reading.py --model model.tflite --regions \"[[10,10,50,50], [60,60,100,100]]\" --image_source sample.jpg")


def main():
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Meter Reader", add_help=False)
    parser.add_argument("--help", action="store_true", help="Show this help message and exit")
    parser.add_argument("--model", default="model.tflite", help="Path to the TensorFlow Lite model")
    parser.add_argument("--regions", required=True, help="Path to the JSON file or a string representation of a list of regions")
    parser.add_argument("--image_source", default="sample.jpg", help="Path to the local image file or URL of the remote image")
    parser.add_argument("--no-gui", action="store_true", help="Disable GUI (no image display)")
    parser.add_argument("--no-output-image", action="store_true", help="Do not save the output image with annotations")

    # Parse the arguments
    args, _ = parser.parse_known_args()

    # Show help and exit if --help is specified
    if args.help:
        print_help()
        sys.exit(0)

    # Check if required arguments are missing
    if not args.model or not args.regions or not args.image_source:
        logging.error("Missing required arguments.")
        print_help()
        sys.exit(1)

    # Validate the arguments
    if not validate_args(args):
        print_help()
        sys.exit(1)

    # Initialize the MeterReader
    meter_reader = MeterReader(args.model)

    # Load the image (local or remote)
    image = load_image(args.image_source)
    if image is None:
        logging.error(f"Unable to load image from {args.image_source}.")
        sys.exit(1)

    # Load regions from the file or list
    regions = load_regions(args.regions)
    if not regions:
        logging.error("No valid regions provided.")
        sys.exit(1)

    # Extract the regions from the image
    image_regions = []
    for (x1, y1, x2, y2) in regions:
        # Ensure the region is within the image bounds
        if x1 < 0 or y1 < 0 or x2 > image.shape[1] or y2 > image.shape[0]:
            logging.warning(f"Region {[x1, y1, x2, y2]} is outside the image bounds. Skipping.")
            continue
        region = image[y1:y2, x1:x2]
        if region.size == 0:
            logging.warning(f"Region {[x1, y1, x2, y2]} is empty. Skipping.")
            continue
        image_regions.append(region)

    if not image_regions:
        logging.error("No valid regions to process.")
        sys.exit(1)

    # Predict the meter reading for each region
    raw_meter_readings = []  # Store raw readings
    processed_meter_readings = []  # Store processed readings
    for region in image_regions:
        try:
            raw_reading = meter_reader.predict(region)
            raw_meter_readings.append(raw_reading)

            # Preprocess the reading
            processed_reading = round(raw_reading)  # Round to the nearest integer
            if processed_reading == 10:  # Handle the special case
                processed_reading = 0
            processed_meter_readings.append(processed_reading)
        except Exception as e:
            logging.error(f"Error processing region: {e}")
            continue

    # Concatenate the processed meter readings into a single integer
    concatenated_readings = int(''.join(map(str, processed_meter_readings)))

    # Print the raw and final results
    logging.info(f"Raw Meter Readings: {raw_meter_readings}")
    logging.info(f"Processed Meter Readings: {processed_meter_readings}")
    logging.info(f"Final Meter Reading: {concatenated_readings}")

    # Visualize the results (if not disabled)
    if not args.no_output_image:
        result_image = meter_reader.visualize(image, regions, raw_meter_readings, raw=True)
        cv2.imwrite("result.jpg", result_image)

    # Display the result (if not disabled)
    if not args.no_gui and not args.no_output_image:
        cv2.imshow("Meter Readings", result_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()