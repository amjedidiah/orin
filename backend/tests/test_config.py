from pathlib import Path

from orin.config import Settings


def test_empty_env_values_count_as_unset(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("ORIN_OWNER_TOKEN=\nBASETEN_BASE_URL=\nMODEL_API_KEY=\n")

    settings = Settings(_env_file=env)  # pyright: ignore[reportCallIssue]

    assert settings.orin_owner_token is None
    assert settings.baseten_base_url is None
    assert settings.model_api_key is None


def test_set_env_values_are_read(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("ORIN_OWNER_TOKEN=s3cret\n")

    settings = Settings(_env_file=env)  # pyright: ignore[reportCallIssue]

    assert settings.orin_owner_token is not None
    assert settings.orin_owner_token.get_secret_value() == "s3cret"
