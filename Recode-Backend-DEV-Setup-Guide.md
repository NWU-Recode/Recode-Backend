# Recode Backend – Setup Guide

---

## 1. Git Branching Strategy

To keep the codebase clean and collaboration simple, always work from the `dev` branch and never commit directly to `main` or `dev`.

**Branch Structure:**

- **`main`**: Stable, production-ready code. No direct commits—only merges from `dev` after testing and review.
- **`dev`**: All development happens here. Feature and fix branches are merged into `dev` via pull requests.
- **Feature branches:** For new features. Name as `feat/<short-feature-description>`, e.g., `feat/user-auth`.
- **Bugfix branches:** For bug fixes. Name as `fix/<short-bug-description>`, e.g., `fix/login-error`.
- **Other types:** Use `hotfix/`, `docs/`, or `refactor/` as needed, e.g., `hotfix/deploy-issue`, `docs/setup-guide`.

**Workflow:**

1. Always start by switching to `dev` and pulling the latest changes:
   ```sh
   git checkout dev
   git pull origin dev
   ```
2. Create your feature/fix branch from `dev`:
   ```sh
   git checkout -b feat/<short-description>
   # or
   git checkout -b fix/<short-description>
   ```
3. Push your branch and open a Pull Request (PR) to merge into `dev`.
4. Only leads/maintainers merge `dev` into `main` after code is tested and reviewed.

**Key Points:**

- Never work directly on `main` or `dev`.
- Name branches clearly and briefly.
- Use Pull Requests for all merges.
- Always pull the latest `dev` before you branch or before merging.

---

## 2. Clone the Repository

Open a terminal and run:

```sh
git clone https://github.com/NWU-Recode/Recode-Backend.git
cd Recode-Backend
```

---

## 2. Set Up Python Virtual Environment

Create and activate your Python venv:

```sh
python -m venv venv
```

- **Windows:**
  ```sh
  .venv\Scripts\activate
  # or if your folder is named "venv"
  venv\Scripts\activate
  ```

---

## 3. Install Python Dependencies

```sh
pip install -r requirements.txt
```

---

## 4. Install Supabase CLI (Windows – Scoop Method)

### A. Install Scoop (if you don’t have it)

Open PowerShell as Administrator:

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
iwr -useb get.scoop.sh | iex
```

### B. Add Supabase Scoop Bucket and Install

```powershell
scoop bucket add supabase https://github.com/supabase/scoop-bucket.git
scoop install supabase
```

### C. Confirm Installation

Open a new terminal and check:

```sh
supabase --version
```

You should see a version number if installed successfully.

---

## 5. Set Up Environment Variables

Copy the example env file and edit it:

```sh
cp .env.template .env
```

Edit `.env` in a text editor and set `SUPABASE_URL` and `SUPABASE_KEY` with your actual values from the Supabase dashboard.

---

## 6. (Optional) Initialize Supabase Migrations

If you plan to manage migrations (otherwise skip):

```sh
supabase init
supabase migration new create_users_table
```

- Edit your migration file in `supabase/migrations/` to define the schema.
- Apply the migration:
  ```sh
  supabase db push
  ```

---

## 7. Start the FastAPI Server

Run from the project root:

```sh
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

---

## 8. Test the Users Endpoint

- Open Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Test endpoint: [http://localhost:8000/users/](http://localhost:8000/users/)

Or use curl:

```sh
curl http://localhost:8000/users/
```

If your Supabase `users` table has data, it will return all users as JSON.

---

## 9. Git Branching Strategy

To keep the codebase clean and make collaboration easy, use the following simple git branching strategy:

- **`main`** (or `master`): Stable, production-ready code only. Deployments and releases come from here.
- **`dev`**: All new features and bug fixes are merged here for testing before going to main.
- **Feature branches:** For new features. Name as `feat/<short-feature-description>`, e.g., `feat/user-auth`.
- **Bugfix branches:** For bug fixes. Name as `fix/<short-bug-description>`, e.g., `fix/login-error`.
- **Other types:** Use `hotfix/`, `docs/`, or `refactor/` as needed, e.g., `hotfix/deploy-issue`, `docs/setup-guide`.

**Workflow Example:**

1. Pull the latest changes:
   ```sh
   git checkout dev
   git pull origin dev
   ```
2. Create your branch:
   ```sh
   git checkout -b feat/<short-description>
   # or
   git checkout -b fix/<short-description>
   ```
3. Push your branch and open a Pull Request to `dev`.
4. Once tested and reviewed, `dev` is merged into `main` for release.

**Key Points:**

- Never commit directly to `main` or `dev`.
- Keep branch names clear and short.
- Always pull latest changes before creating a new branch.
- Use Pull Requests for all merges (no direct pushes).

---

# Setup Complete

You now have a fully working local backend ready for development and testing.

