# CAPTCHA Labeling Tool

![Example](example.png)

A Flask-based web application for labeling CAPTCHA images. This tool allows users to view CAPTCHA images, enter their corresponding labels, and save the labels to a JSON file.

## Features

- View CAPTCHA images stored in the `src/static/img` directory.
- Label the images and save the labels to a JSON file (`src/static/labels.json`).
- Automatically jump to the next CAPTCHA after entering a label (optional).
- Filter allowable characters using a regular expression.
- Hide labeled images for easier navigation.

## Setup

Follow these steps to set up and run the CAPTCHA Labeling Tool on your local machine.

### Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/yourusername/captcha-labeling-tool.git
    cd captcha-labeling-tool
    ```

2. **Install dependencies:**

   Install the required Python packages using `pip`:

    ```bash
    pip install -r requirements.txt
    ```

3. **Add CAPTCHA images:**

   Place your CAPTCHA images in the `src/static/img` directory. Ensure the images are named appropriately (e.g., `captcha_sample_1.jpg`, `captcha_sample_2.jpg`, etc.).

4. **Run the Flask app:**

   Navigate to the `src` directory and start the Flask development server:

    ```bash
    cd src
    python app.py
    ```

   The app will be available at `http://127.0.0.1:5000/`.

## Usage

1. Open your web browser and navigate to `http://127.0.0.1:5000/`.
2. You will see a list of CAPTCHA images displayed in a table.
3. Enter the corresponding label for each image in the input field below it.
4. Use the following features to enhance your labeling experience:
   - **Auto-Tab**: Select the number of characters in the CAPTCHA to automatically jump to the next image after entering the label and save them automatically.
   - **Allowable Characters**: Specify a regular expression (e.g., `0-9a-z`) to restrict input to specific characters.
   - **Hide Labeled Images**: Check the box to hide images that already have labels.
5. Click `Save Cache` to save the labels to `src/static/labels.json`.

## File Structure

The project has the following structure:

```
captcha-labeling-tool/
├── LICENSE                  # License file
├── README.md                # Project documentation
├── requirements.txt         # Python dependencies
└── src/                     # Source code directory
    ├── app.py               # Main Flask application
    ├── static/              # Static files
    │   ├── img/             # Directory for CAPTCHA images
    │   └── labels.json      # JSON file to store labels
    └── templates/           # HTML templates
        └── index.html       # Main HTML template
```

## Example

### Adding CAPTCHA Images

Place your CAPTCHA images in the `src/static/img` directory. For example:

```
src/
└── static/
    └── img/
        ├── captcha_sample_1.jpg
        ├── captcha_sample_2.jpg
        └── captcha_sample_3.jpg
```

### Saving Labels

After entering labels for the images, click `Save Cache`. The labels will be saved in `src/static/labels.json` in the following format:

```json
{
  "captcha_sample_1.jpg": "p7xgy",
  "captcha_sample_2.jpg": "6c3fn",
  "captcha_sample_3.jpg": "883pm"
}
```

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvements, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
