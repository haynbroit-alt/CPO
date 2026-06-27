import time
from typing import Optional

import docker
from docker.errors import ContainerError, DockerException

from app.models import CPO, ExecutionResult
from config import EXECUTION_TIMEOUT, WORLD_IMAGES, DEFAULT_WORLD


def _image_for(cpo: CPO) -> str:
    # Caller-supplied image takes precedence over world default
    if cpo.execution_spec.image:
        return cpo.execution_spec.image
    return WORLD_IMAGES.get(cpo.world, WORLD_IMAGES[DEFAULT_WORLD])


def _timeout_for(cpo: CPO) -> int:
    return int(cpo.execution_spec.constraints.get("timeout", EXECUTION_TIMEOUT))


def _memory_for(cpo: CPO) -> str:
    mb = int(cpo.execution_spec.constraints.get("memory_mb", 128))
    return f"{mb}m"


def execute(cpo: CPO) -> ExecutionResult:
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
            # Prevent privilege escalation
            security_opt=["no-new-privileges:true"],
        )

        status = container.wait(timeout=timeout)
        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        exit_code: int = status.get("StatusCode", 0)

    except ContainerError as exc:
        stdout = ""
        stderr = str(exc)
        exit_code = 1
    except DockerException as exc:
        stdout = ""
        stderr = f"Docker error: {exc}"
        exit_code = 1
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass

    runtime_ms = (time.monotonic() - start) * 1000
    return ExecutionResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        runtime_ms=round(runtime_ms, 2),
    )
