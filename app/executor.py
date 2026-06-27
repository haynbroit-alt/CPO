"""Sandbox execution router.

Two backends are supported:
- "docker"     — isolated container (network off, read-only FS, mem cap).  Requires Docker socket.
- "subprocess" — direct Python subprocess.  For demo / Render deployments without Docker.
                 WARNING: no network or filesystem isolation.  Do not use with untrusted code.
"""
import subprocess
import time

try:
    import docker
    from docker.errors import ContainerError, DockerException
except ImportError:
    docker = None  # type: ignore[assignment]
    ContainerError = DockerException = Exception  # type: ignore[assignment,misc]

from app.models import CPO, ExecutionResult
from config import EXECUTION_TIMEOUT, EXECUTOR_BACKEND, WORLD_IMAGES, DEFAULT_WORLD


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _timeout_for(cpo: CPO) -> int:
    return int(cpo.execution_spec.constraints.get("timeout", EXECUTION_TIMEOUT))


def _memory_for(cpo: CPO) -> str:
    mb = int(cpo.execution_spec.constraints.get("memory_mb", 128))
    return f"{mb}m"


def _image_for(cpo: CPO) -> str:
    if cpo.execution_spec.image:
        return cpo.execution_spec.image
    return WORLD_IMAGES.get(cpo.world, WORLD_IMAGES[DEFAULT_WORLD])


# ---------------------------------------------------------------------------
# Docker backend
# ---------------------------------------------------------------------------

def _execute_docker(cpo: CPO) -> ExecutionResult:
    image = _image_for(cpo)
    timeout = _timeout_for(cpo)
    memory = _memory_for(cpo)

    client = docker.from_env()
    container = None
    start = time.monotonic()

    try:
        container = client.containers.run(
            image=image,
            command=["python", "-c", cpo.code],
            detach=True,
            network_disabled=True,
            mem_limit=memory,
            read_only=True,
            security_opt=["no-new-privileges:true"],
        )
        status = container.wait(timeout=timeout)
        stdout = container.logs(stdout=True,  stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        exit_code: int = status.get("StatusCode", 0)

    except ContainerError as exc:
        stdout, stderr, exit_code = "", str(exc), 1
    except DockerException as exc:
        stdout, stderr, exit_code = "", f"Docker error: {exc}", 1
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass

    return ExecutionResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        runtime_ms=round((time.monotonic() - start) * 1000, 2),
    )


# ---------------------------------------------------------------------------
# Subprocess backend (no isolation — demo / Render deployments only)
# ---------------------------------------------------------------------------

def _execute_subprocess(cpo: CPO) -> ExecutionResult:
    timeout = _timeout_for(cpo)
    start = time.monotonic()

    try:
        proc = subprocess.run(
            ["python", "-c", cpo.code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout   = proc.stdout
        stderr   = proc.stderr
        exit_code = proc.returncode

    except subprocess.TimeoutExpired:
        stdout, stderr, exit_code = "", f"Execution timed out after {timeout}s", 1
    except Exception as exc:
        stdout, stderr, exit_code = "", str(exc), 1

    return ExecutionResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        runtime_ms=round((time.monotonic() - start) * 1000, 2),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def execute(cpo: CPO) -> ExecutionResult:
    if EXECUTOR_BACKEND == "subprocess":
        return _execute_subprocess(cpo)
    return _execute_docker(cpo)
