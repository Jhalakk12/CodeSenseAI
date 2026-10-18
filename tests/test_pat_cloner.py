import pytest
import os

def format_auth_clone_url(git_url: str, token: str) -> str:
    clean_url = git_url.strip()
    if token:
        token = token.strip()
        if "github.com" in clean_url:
            repo_part = clean_url.split("github.com")[-1].lstrip("/:")
            if not repo_part.endswith(".git"):
                repo_part += ".git"
            return f"https://x-access-token:{token}@github.com/{repo_part}"
        else:
            return clean_url.replace("https://", f"https://x-access-token:{token}@")
    return clean_url

def sanitize_git_output(output: str, token: str) -> str:
    if token and token in output:
        return output.replace(token, "******")
    return output

def test_public_repo_url_unchanged():
    url = "https://github.com/pallets/flask"
    assert format_auth_clone_url(url, "") == url

def test_private_repo_authenticated_url_formatting():
    url = "https://github.com/KiranKhatter/my-private-project"
    token = "ghp_MockSecretToken123456789"
    auth_url = format_auth_clone_url(url, token)
    assert auth_url == "https://x-access-token:ghp_MockSecretToken123456789@github.com/KiranKhatter/my-private-project.git"
    assert token in auth_url

def test_token_sanitization_in_logs():
    token = "ghp_MockSecretToken123456789"
    raw_error = f"fatal: could not read Username for 'https://x-access-token:{token}@github.com': No such device"
    sanitized = sanitize_git_output(raw_error, token)
    assert token not in sanitized
    assert "******" in sanitized
