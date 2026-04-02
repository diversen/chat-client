from chat_client.tools.python_runtime import NO_RESULT_ERROR, run_python_in_docker, validate_code_input


def python_hardened(
    code: str,
    docker_image: str | None = None,
    attachment_host_dir: str | None = None,
) -> str:
    """
    Execute Python code in a hardened Docker container and return output/result.
    """
    validation_error = validate_code_input(code)
    if validation_error:
        return validation_error

    return run_python_in_docker(
        code,
        docker_image,
        [
            "--network",
            "none",
            "--init",
            "--rm",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--cap-drop=ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory=256m",
            "--memory-swap=256m",
            "--cpus=0.5",
            "--pids-limit=128",
            "--ulimit",
            "nproc=128:128",
            "--ulimit",
            "stack=67108864",
            "--user",
            "65534:65534",
        ],
        attachment_host_dir=attachment_host_dir,
    )


def python_relaxed(
    code: str,
    docker_image: str | None = None,
    attachment_host_dir: str | None = None,
) -> str:
    """
    Execute Python code in Docker with minimal restrictions for local testing.
    """
    validation_error = validate_code_input(code)
    if validation_error:
        return validation_error

    return run_python_in_docker(
        code,
        docker_image,
        [
            "--init",
            "--rm",
        ],
        attachment_host_dir=attachment_host_dir,
    )
