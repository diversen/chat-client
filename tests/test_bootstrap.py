from chat_client.core import bootstrap


def test_ensure_runtime_config_creates_data_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = bootstrap.ensure_runtime_config()

    assert result.created is True
    assert result.data_dir == (tmp_path / "data").resolve()
    assert result.config_path == (tmp_path / "data" / "config.py").resolve()
    assert result.config_path.exists()

    second_result = bootstrap.ensure_runtime_config()

    assert second_result.created is False


def test_ensure_runtime_config_prompts_before_creating(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bootstrap, "can_prompt_for_user", lambda: True)

    prompts = []
    monkeypatch.setattr(bootstrap.click, "echo", prompts.append)
    monkeypatch.setattr(bootstrap.click, "confirm", lambda text, default=True: True)

    result = bootstrap.ensure_runtime_config(prompt_before_create=True)

    assert result.created is True
    assert prompts == ["No runtime config found at data/config.py."]


def test_ensure_runtime_config_aborts_when_creation_is_declined(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bootstrap, "can_prompt_for_user", lambda: True)
    monkeypatch.setattr(bootstrap.click, "echo", lambda text: None)
    monkeypatch.setattr(bootstrap.click, "confirm", lambda text, default=True: False)

    try:
        bootstrap.ensure_runtime_config(prompt_before_create=True)
    except bootstrap.click.ClickException as exc:
        assert str(exc) == "Aborted before creating runtime config."
    else:
        raise AssertionError("Expected runtime config creation to abort.")

    assert not (tmp_path / "data").exists()


def test_ensure_runtime_config_requires_init_when_creation_is_disallowed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    try:
        bootstrap.ensure_runtime_config(allow_create=False)
    except bootstrap.click.ClickException as exc:
        assert str(exc) == "System is not initialized. Run `chat-client init-system` first."
    else:
        raise AssertionError("Expected runtime config creation to be blocked.")

    assert not (tmp_path / "data").exists()


def test_maybe_prompt_for_initial_user_creates_user(monkeypatch):
    monkeypatch.setattr(bootstrap, "can_prompt_for_user", lambda: True)

    prompts = iter(["admin@example.com", "Password123!"])
    monkeypatch.setattr(bootstrap.click, "confirm", lambda text, default=True: True)
    monkeypatch.setattr(
        bootstrap.click,
        "prompt",
        lambda text, **kwargs: next(prompts),
    )

    created = {}

    async def fake_count_users():
        return 0

    async def fake_create_user(email, password):
        created["email"] = email
        created["password"] = password
        return True

    monkeypatch.setattr(bootstrap, "count_users", fake_count_users)
    monkeypatch.setattr(bootstrap, "create_local_user", fake_create_user)

    message = bootstrap.maybe_prompt_for_initial_user()

    assert created == {"email": "admin@example.com", "password": "Password123!"}
    assert message == "Created initial user: admin@example.com"


def test_maybe_prompt_for_initial_user_skips_when_not_interactive(monkeypatch):
    monkeypatch.setattr(bootstrap, "can_prompt_for_user", lambda: False)

    message = bootstrap.maybe_prompt_for_initial_user()

    assert message == "Skipped initial user creation because no interactive terminal was detected."


def test_runtime_bootstrap_result_formats_messages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_bootstrap = bootstrap.ConfigBootstrapResult(
        created=True,
        data_dir=(tmp_path / "data").resolve(),
        config_path=(tmp_path / "data" / "config.py").resolve(),
    )
    result = bootstrap.RuntimeBootstrapResult(
        config_bootstrap=config_bootstrap,
        database_path=(tmp_path / "data" / "database.db").resolve(),
        database_created=True,
        user_message="Created initial user: admin@example.com",
    )

    assert result.messages() == [
        f"Created default config at {(tmp_path / 'data' / 'config.py').resolve()}",
        f"Initialized database at {(tmp_path / 'data' / 'database.db').resolve()}",
        "Created initial user: admin@example.com",
    ]
