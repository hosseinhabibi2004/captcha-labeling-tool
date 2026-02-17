# CAPTCHA Labeling Tool

![Example](example.png)

A Flask-based web application for labeling CAPTCHA images. This tool supports **multiple sites**: each site has its own folder with images and labels. Users select a site, view that site's captchas, and labels are saved per site.

## Features

- **Multi-site support** – Organize captchas by site; each site has its own `img/` and `labels.json`.
- **Site selector** – Choose a site to label only that site's images.
- **Bucket-based distribution** – Multi-user labeling with buckets assigned per session per site.
- **User authentication** – Simple username/password login system to track who labeled each image.
- **User tracking** – Each label records which user created it (`labeled_by`).
- **Admin review** – Admins can review labels and mark them as "Sure" or "Not Sure" (records `reviewed_by`).
- **User management** – Admins can create, edit, and delete users through the admin panel.
- **Auto-save** – Labels are saved automatically (with optional manual Save Cache).
- **Auto-Tab** – Optionally jump to the next CAPTCHA after entering a label.
- **Allowable characters** – Restrict input with a regular expression (e.g. `0-9a-z`).
- **Hide labeled images** – Option to hide already-labeled rows.
- **Admin review panel** – Review and mark labels as "Sure" or "Not Sure", with optional site filter.

## Setup

### Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/yourusername/captcha-labeling-tool.git
    cd captcha-labeling-tool
    ```

2. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3. **Create storage folders (one per site):**

   Create a base directory (default: `storage/` in the project root). Each **site** is a subfolder containing an `img/` directory and (after labeling) a `labels.json` file. Example:

    ```txt
    storage/
    ├── site_a/
    │   └── img/
    │       ├── captcha_1.jpg
    │       └── captcha_2.jpg
    └── site_b/
        └── img/
            └── ...
    ```

   You can override the base directory with the `RESULTS_BASE_DIR` environment variable.

4. **Initial setup:**

   On first run, the app will redirect you to a setup page where you need to create the first admin user:
   - Enter a username and password
   - Confirm the password
   - Click "Create Admin Account"

   **Note:** The first user created is automatically granted admin privileges. You can create additional users (admin or regular) through the User Management section in the admin panel after logging in.

5. **Run the Flask app:**

    ```bash
    cd src
    python app.py
    ```

   The app will be available at `http://127.0.0.1:5000/` (or `http://0.0.0.0:5000/`).

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RESULTS_BASE_DIR` | `../storage` (relative to `src/`) | Base directory for site folders and users.json. |
| `BUCKET_SIZE` | `20` | Number of images per bucket. |

## Usage

### Labeling Images

1. Open `http://127.0.0.1:5000/`.
2. **Login** with your username and password (default: `admin` / `admin`).
3. **Select a site** from the dropdown. The page loads that site's bucket of images.
4. Enter the label for each CAPTCHA in the input field (or use "Mark as Empty" for unreadable images).
5. Labels auto-save; you can also click **Save Cache** to force save.
6. Use **Request New Bucket** to get another set of images for the same site when the current bucket is done.
7. Optional: **Auto-Tab**, **Allowable Characters**, and **Hide labeled images** in the options area.

**Note:** Each label you create is automatically tagged with your username (`labeled_by` field).

### Admin Panel

1. Open `http://127.0.0.1:5000/admin` and login with an admin account.
2. **Review labeled images:**
   - Use **Filter by Site** to show one site or "All Sites".
   - See who labeled each image in the "Labeled By" column.
   - Mark each label as **Sure** or **Not Sure** and click **Save All Reviews**.
   - Your review is recorded in the "Reviewed By" column.

3. **Manage users:**
   - Scroll to the "User Management" section at the bottom.
   - **Add new users:** Enter username, password, and check "Admin" if they should have admin access.
   - **Edit users:** Click "Edit" on any user to modify their password or admin status.
   - **Delete users:** Click "Delete" to remove a user (you cannot delete your own account).

## File structure

### Project layout

```txt
captcha-labeling-tool/
├── LICENSE
├── README.md
├── requirements.txt
├── storage/                 # Base dir for sites (configurable)
│   ├── users.json           # User accounts (auto-created)
│   ├── site_a/
│   │   ├── img/             # CAPTCHA images for this site
│   │   ├── labels.json      # Labels for this site
│   │   └── buckets.json     # Bucket state (auto-created)
│   └── site_b/
│       ├── img/
│       └── labels.json
└── src/
    ├── app.py               # Flask app and API
    ├── auth.py              # Authentication and user management
    ├── bucket_manager.py    # Per-site bucket logic
    ├── file_lock.py        # Safe JSON read/write
    ├── sites.py             # Site discovery and paths
    └── templates/
        ├── index.html       # Labeling UI
        ├── admin.html       # Admin review UI
        ├── login.html       # Login page
        └── setup.html       # First-time setup page
```

### Labels format (per site)

Each site's `labels.json` stores labels in one of two formats:

**Legacy flat format** (backward compatible):

```json
{
  "captcha_1.jpg": "p7xgy",
  "captcha_2.jpg": "6c3fn",
  "captcha_3.jpg": "__NULL__"
}
```

**Extended nested format** (with user tracking):

```json
{
  "captcha_1.jpg": {
    "value": "p7xgy",
    "labeled_by": "alice"
  },
  "captcha_2.jpg": {
    "value": "6c3fn",
    "labeled_by": "bob",
    "admin_review": {
      "status": "sure",
      "reviewed_by": "admin"
    }
  },
  "captcha_3.jpg": {
    "value": "__NULL__",
    "labeled_by": "alice"
  }
}
```

- `value`: The label text (or `"__NULL__"` for empty/unreadable images)
- `labeled_by`: Username of the user who created the label (added automatically)
- `admin_review.status`: `"sure"` or `"not_sure"` (set by admins)
- `admin_review.reviewed_by`: Username of the admin who reviewed the label

**Note:** New labels are automatically saved in the nested format with `labeled_by`. Existing flat labels remain compatible and are converted to nested format when updated.

### User accounts

User accounts are stored in `storage/users.json`:

```json
[
  {
    "username": "admin",
    "password": "admin",
    "is_admin": true
  },
  {
    "username": "labeler1",
    "password": "password123",
    "is_admin": false
  }
]
```

**First-time setup:** If `storage/users.json` doesn't exist or is empty, the app will redirect to `/setup` where you can create the first admin user. The first user created is automatically granted admin privileges.

**Security Note:** Passwords are stored in plain text. This is intentional for simplicity in a local tool. For production deployments, consider implementing password hashing.

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvements, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
