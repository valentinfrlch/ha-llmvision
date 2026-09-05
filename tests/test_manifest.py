"""Unit tests for manifest.json configuration and dependency compatibility.

This test module validates:
1. manifest.json structure and format
2. Requirements follow PEP 508 standard and avoid strict pinning (==)
3. Critical dependencies use flexible versioning (>= not ==)
4. All required dependencies can be imported dynamically
5. Required API methods exist and are callable
6. Real runtime execution behavior for async I/O and DB dependencies
"""
import json
from importlib import import_module
from pathlib import Path

import pytest
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

# Module-level constant for manifest path
MANIFEST_PATH = (
    Path(__file__).parent.parent
    / "custom_components"
    / "llmvision"
    / "manifest.json"
)

# Dependencies with their critical API surface
DEPENDENCIES_API_CHECK = {
    "aiofile": ("async_open",),
    "aiosqlite": ("connect",),
    "boto3": ("client",),
}

# Dependencies that should use flexible versioning (>=) not strict (==)
FLEXIBLE_VERSION_DEPENDENCIES = {"aiofile", "aiosqlite", "boto3"}


@pytest.fixture
def manifest_data():
    """Load manifest.json from file."""
    with open(MANIFEST_PATH) as f:
        return json.load(f)


@pytest.fixture
def requirements_list(manifest_data):
    """Parse requirements from manifest into Requirement objects."""
    requirements = {}
    for req_str in manifest_data.get("requirements", []):
        try:
            req = Requirement(req_str)
            requirements[req.name] = req
        except InvalidRequirement as e:
            pytest.fail(f"Invalid requirement {req_str}: {e}")
    return requirements


class TestManifestStructure:
    """Test manifest.json file structure and format."""

    @pytest.mark.unit
    def test_manifest_file_exists(self):
        """Test that manifest.json file exists at expected location."""
        assert MANIFEST_PATH.exists(), f"manifest.json not found at {MANIFEST_PATH}"

    @pytest.mark.unit
    def test_manifest_is_valid_json(self):
        """Test that manifest.json is valid JSON format."""
        with open(MANIFEST_PATH) as f:
            try:
                json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"manifest.json is not valid JSON: {e}")

    @pytest.mark.unit
    def test_manifest_has_required_fields(self, manifest_data):
        """Test that manifest has all required Home Assistant fields."""
        required_fields = {"domain", "name", "requirements", "version"}
        missing = required_fields - set(manifest_data.keys())
        assert not missing, f"manifest.json missing required fields: {missing}"

    @pytest.mark.unit
    def test_requirements_is_list(self, manifest_data):
        """Test that requirements field is a list."""
        requirements = manifest_data.get("requirements")
        assert isinstance(requirements, list), "requirements must be a list"
        assert len(requirements) > 0, "requirements list cannot be empty"


class TestRequirementsFormat:
    """Test that all requirements follow PEP 508 standard and avoid strict pinning."""

    @pytest.mark.unit
    def test_all_requirements_are_valid_pep508(self, manifest_data):
        """Test that all requirements are valid PEP 508 format.

        This ensures:
        - Package names are valid
        - Version specifiers use correct syntax
        - No malformed strings like ">aiofile3.9.0" or "aiofile>==3.9.0"
        """
        for req_str in manifest_data["requirements"]:
            try:
                req = Requirement(req_str)
                assert req.name, f"requirement {req_str} has no package name"
                assert req.specifier, f"requirement {req_str} has no version specifier"
            except InvalidRequirement as e:
                pytest.fail(f"requirement {req_str} is malformed PEP 508: {e}")

    @pytest.mark.unit
    def test_version_specifiers_are_valid_semver(self, requirements_list):
        """Test that all version specifiers contain valid semantic versions."""
        for pkg_name, req in requirements_list.items():
            for spec in req.specifier:
                try:
                    Version(spec.version)
                except InvalidVersion as e:
                    pytest.fail(
                        f"{pkg_name} has invalid version '{spec.version}': {e}"
                    )

    @pytest.mark.unit
    def test_no_strict_version_pinning(self, requirements_list):
        """Test that NO dependency in manifest.json uses strict '==' pinning.

        Strict pinning (==) causes conflicts with Home Assistant Core/Beta versions
        that pre-install or upgrade dependencies. Flexible versions (>=) must be used.
        """
        strict_pinned = []
        for pkg_name, req in requirements_list.items():
            for spec in req.specifier:
                if spec.operator == "==":
                    strict_pinned.append(f"{pkg_name} ({spec})")

        assert not strict_pinned, (
            f"The following dependencies use strict '==' pinning: {strict_pinned}. "
            f"Use flexible versioning ('>=') to avoid Home Assistant dependency conflicts."
        )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "pkg_name",
        list(FLEXIBLE_VERSION_DEPENDENCIES),
        ids=lambda x: f"flexible_version_{x}",
    )
    def test_critical_dependencies_use_flexible_versioning(
        self, requirements_list, pkg_name
    ):
        """Test that critical dependencies use >= not ==.

        Strict pinning (==) causes conflicts with Home Assistant beta versions
        that pre-install dependencies. Flexible versions (>=) are safer.

        Parameters:
            pkg_name: Package name to check (aiofile, aiosqlite, boto3)
        """
        assert (
            pkg_name in requirements_list
        ), f"{pkg_name} not found in requirements"

        req = requirements_list[pkg_name]
        has_flexible = any(spec.operator == ">=" for spec in req.specifier)

        assert has_flexible, (
            f"{pkg_name} should use '>=' versioning (flexible), "
            f"but has '{req.specifier}' (strict). "
            f"Strict pinning (==) causes conflicts with Home Assistant beta versions."
        )


class TestDependencyImports:
    """Test that required dependencies can be imported at runtime."""

    @pytest.mark.unit
    def test_all_manifest_dependencies_can_be_imported(self, requirements_list):
        """Test that every dependency declared in manifest.json can be imported.

        Automatically discovers and tests all requirements in manifest.json.
        """
        for pkg_name in requirements_list:
            try:
                import_module(pkg_name)
            except ImportError as e:
                pytest.fail(
                    f"Failed to import requirement '{pkg_name}': {e}. "
                    "This indicates a missing dependency or invalid package name in manifest.json."
                )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "module_name,api_methods",
        [
            (module_name, methods)
            for module_name, methods in DEPENDENCIES_API_CHECK.items()
        ],
        ids=lambda x: f"api_{x[0]}",
    )
    def test_dependency_has_required_api(self, module_name, api_methods):
        """Test that each dependency has the required API methods.

        This catches version bumps that break the API we depend on.

        Parameters:
            module_name: Name of the module
            api_methods: Tuple of required method names in that module
        """
        try:
            module = import_module(module_name)
        except ImportError as e:
            pytest.fail(f"Cannot import {module_name}: {e}")

        for method_name in api_methods:
            assert hasattr(
                module, method_name
            ), f"{module_name} missing {method_name} method"
            assert callable(
                getattr(module, method_name)
            ), f"{module_name}.{method_name} is not callable"


class TestDependencyRuntimeBehavior:
    """Test actual runtime execution of critical dependencies to catch breaking changes."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_aiofile_async_write_and_read(self, tmp_path):
        """Verify that aiofile.async_open works with the async context manager syntax used in media_handlers."""
        from aiofile import async_open

        test_file = tmp_path / "test_async_io.txt"
        test_data = b"llmvision-dependency-verification"

        async with async_open(str(test_file), "wb") as f:
            await f.write(test_data)

        assert test_file.exists()
        assert test_file.read_bytes() == test_data

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_aiosqlite_async_connection_and_query(self):
        """Verify that aiosqlite can execute basic async queries in memory."""
        import aiosqlite

        async with aiosqlite.connect(":memory:") as db:
            cursor = await db.execute("SELECT 1 + 1")
            result = await cursor.fetchone()
            assert result == (2,)

    @pytest.mark.unit
    def test_boto3_session_and_client_factory(self):
        """Verify that boto3 session and client creation interface is functional."""
        import boto3
        from botocore.config import Config

        session = boto3.Session(
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1",
        )
        client = session.client("bedrock-runtime", config=Config(signature_version="v4"))
        assert hasattr(client, "invoke_model")
