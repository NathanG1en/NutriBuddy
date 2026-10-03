import os
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    # 1. Check for gcloud
    if not shutil.which("gcloud"):
        print("\n❌ Error: 'gcloud' CLI is not found.")
        print("Please install it using Homebrew:")
        print("\n    brew install --cask google-cloud-sdk")
        print("\nThen restart your terminal and run this script again.")
        sys.exit(1)

    # 2. Extract Env Vars
    env_vars = []
    env_path = Path(".env")
    if env_path.exists():
        print("✅ Reading .env file...")
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Skip comments or invalid lines
                if "=" in line:
                    # Basic parsing: take key=val
                    key_part = line.split("=")[0].strip()
                    # Exclude local-only credentials (Cloud Run uses ADC)
                    if key_part == "GOOGLE_APPLICATION_CREDENTIALS":
                        continue

                    pair = line.split("#")[0].strip()
                    env_vars.append(pair)
    else:
        print("⚠️ Warning: No .env file found!")

    env_flag = ""
    if env_vars:
        print(f"   Found {len(env_vars)} environment variables.")
        # Join with comma
        env_string = ",".join(env_vars)
        env_flag = f'--set-env-vars "{env_string}"'

    # 3. Construct Command
    project_id = os.getenv("VITE_FIREBASE_PROJECT_ID")

    # Try to find it in .env if not in os.environ
    if not project_id:
        for v in env_vars:
            if v.startswith("VITE_FIREBASE_PROJECT_ID="):
                project_id = v.split("=")[1]
                break

    # fallback: try gcloud config
    if not project_id or project_id == "YOUR_PROJECT_ID":
        try:
            print("   Attempting to detect project ID from gcloud config...")
            res = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
            )
            val = res.stdout.strip()
            if val and val != "(unset)":
                project_id = val
        except Exception:
            pass

    # fallback: prompt user
    if not project_id or project_id == "YOUR_PROJECT_ID":
        project_id = input(
            "\n🔴 Could not detect Project ID. Please enter your GCP Project ID: "
        ).strip()

    if not project_id:
        print("❌ Error: No Project ID provided. Exiting.")
        sys.exit(1)

    print(f"\n🚀 Preparing deployment for project: {project_id}")

    # 4. Create .env.public for safe build
    public_env_path = Path(".env.public")
    vite_vars = [v for v in env_vars if v.startswith("VITE_")]

    print(
        f"   Generating .env.public with {len(vite_vars)} safe variables for build..."
    )
    with open(public_env_path, "w") as f:
        for v in vite_vars:
            f.write(v + "\n")

    cmd = (
        f"gcloud run deploy nutribuddy "
        f"--source . "
        f"--project {project_id} "
        f"--region us-central1 "
        f"--timeout 300 "
        f"--memory 2Gi "
        f"--allow-unauthenticated "
        f"{env_flag}"
    )

    print("\nCommand to run:")
    print("---------------------------------------------------")
    print(cmd)
    print("---------------------------------------------------")

    confirm = input("\nDo you want to run this command now? (y/n): ")
    if confirm.lower() == "y":
        try:
            subprocess.run(cmd, shell=True, check=True)
            print("\n✅ Deployment command finished.")
        except subprocess.CalledProcessError:
            print("\n❌ Deployment failed.")
        finally:
            # Cleanup
            if public_env_path.exists():
                print("   Cleaning up .env.public...")
                public_env_path.unlink()
    else:
        print("Aborted.")
        # Cleanup just in case
        if public_env_path.exists():
            public_env_path.unlink()


if __name__ == "__main__":
    main()
