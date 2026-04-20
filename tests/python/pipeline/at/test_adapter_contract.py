"""
Tests for AT adapter contract compliance.

These tests verify that the AT adapter exposes the required interface
for the service registry to call. The adapter must:
1. Be importable as "src.python.pipeline.at"
2. Export a callable run_pipeline function
3. Return a dict with "stages" and "dry_run" keys
"""

import importlib


class TestAdapterImportable:
    """Test that the AT adapter module can be imported and exposes required symbols."""

    def test_adapter_importable(self):
        """The AT adapter module should be importable."""
        mod = importlib.import_module("src.python.pipeline.at")
        assert mod is not None

    def test_run_pipeline_is_callable(self):
        """The adapter should export a callable run_pipeline function."""
        mod = importlib.import_module("src.python.pipeline.at")
        assert hasattr(mod, "run_pipeline")
        assert callable(mod.run_pipeline)


class TestRunPipelineSignature:
    """Test that run_pipeline accepts the expected arguments."""

    def test_run_pipeline_accepts_stages(self):
        """run_pipeline should accept a stages argument."""
        from src.python.pipeline.at import run_pipeline

        # Should not raise
        result = run_pipeline(stages="discover", dry_run=True)
        assert result is not None

    def test_run_pipeline_accepts_dry_run(self):
        """run_pipeline should accept a dry_run argument."""
        from src.python.pipeline.at import run_pipeline

        # Should not raise
        result = run_pipeline(stages="", dry_run=True)
        assert result is not None

    def test_run_pipeline_defaults_to_all_stages(self):
        """run_pipeline should default to running all stages."""
        from src.python.pipeline.at import run_pipeline

        result = run_pipeline(dry_run=True)
        assert result is not None
        assert result["stages"] is not None


class TestRunPipelineReturnsDict:
    """Test that run_pipeline returns a dict with the required structure."""

    def test_run_pipeline_returns_dict(self):
        """run_pipeline should return a dict."""
        from src.python.pipeline.at import run_pipeline

        result = run_pipeline(stages="", dry_run=True)
        assert isinstance(result, dict)

    def test_run_pipeline_has_stages_key(self):
        """run_pipeline result should have a 'stages' key."""
        from src.python.pipeline.at import run_pipeline

        result = run_pipeline(stages="discover", dry_run=True)
        assert "stages" in result
        assert isinstance(result["stages"], list)

    def test_run_pipeline_has_dry_run_key(self):
        """run_pipeline result should have a 'dry_run' key."""
        from src.python.pipeline.at import run_pipeline

        result = run_pipeline(stages="", dry_run=True)
        assert "dry_run" in result
        assert isinstance(result["dry_run"], bool)

    def test_run_pipeline_reflects_dry_run_arg(self):
        """The 'dry_run' key in the result should match the argument."""
        from src.python.pipeline.at import run_pipeline

        result_true = run_pipeline(stages="", dry_run=True)
        assert result_true["dry_run"] is True

        result_false = run_pipeline(stages="", dry_run=False)
        assert result_false["dry_run"] is False


class TestStageList:
    """Test that the adapter defines the expected stage list."""

    def test_all_stages_constant_exists(self):
        """The adapter should define an ALL_STAGES constant."""
        import src.python.pipeline.at.orchestrator as orchestrator

        assert hasattr(orchestrator, "ALL_STAGES")
        assert isinstance(orchestrator.ALL_STAGES, list)
        assert len(orchestrator.ALL_STAGES) > 0

    def test_expected_stages_defined(self):
        """The adapter should define the expected stage names."""
        import src.python.pipeline.at.orchestrator as orchestrator

        expected_stages = [
            "discover",
            "extract",
            "content",
            "dose",
            "flowcharts",
            "structure",
            "qualifications",
            "chunk",
            "medications",
            "version",
        ]
        for stage in expected_stages:
            assert stage in orchestrator.ALL_STAGES


class TestDiscoverStage:
    """Test that the discover stage is functional."""

    def test_discover_module_exists(self):
        """The discover module should be importable."""
        mod = importlib.import_module("src.python.pipeline.at.discover")
        assert mod is not None

    def test_discover_site_function_exists(self):
        """The discover module should export a discover_site function."""
        from src.python.pipeline.at.discover import discover_site

        assert callable(discover_site)

    def test_discover_site_returns_discovery_result(self):
        """discover_site should return an ATDiscoveryResult."""
        from src.python.pipeline.at.discover import discover_site

        result = discover_site(output_dir=None)
        # The stub implementation returns an empty result
        assert result is not None
        assert hasattr(result, "guidelines")
        assert hasattr(result, "medicines")
        assert hasattr(result, "categories")


class TestModelsModule:
    """Test that the models module defines the expected schemas."""

    def test_at_guideline_ref_exists(self):
        """The models module should define ATGuidelineRef."""
        from src.python.pipeline.at.models import ATGuidelineRef

        assert ATGuidelineRef is not None

    def test_at_medicine_ref_exists(self):
        """The models module should define ATMedicineRef."""
        from src.python.pipeline.at.models import ATMedicineRef

        assert ATMedicineRef is not None

    def test_at_discovery_result_exists(self):
        """The models module should define ATDiscoveryResult."""
        from src.python.pipeline.at.models import ATDiscoveryResult

        assert ATDiscoveryResult is not None

    def test_at_content_section_exists(self):
        """The models module should define ATContentSection."""
        from src.python.pipeline.at.models import ATContentSection

        assert ATContentSection is not None

    def test_at_flowchart_exists(self):
        """The models module should define ATFlowchart."""
        from src.python.pipeline.at.models import ATFlowchart

        assert ATFlowchart is not None


class TestRunPipelineAllStages:
    """Test that run_pipeline correctly chains all stages in dry-run mode."""

    def test_run_pipeline_all_stages_dry_run(self):
        """run_pipeline with stages='all' and dry_run=True should run all stages without ChromaDB writes."""
        from src.python.pipeline.at import run_pipeline

        result = run_pipeline(stages="all", dry_run=True)
        assert result["stages"] == [
            "discover",
            "extract",
            "content",
            "dose",
            "flowcharts",
            "structure",
            "qualifications",
            "chunk",
            "medications",
            "version",
        ]
        assert result["dry_run"] is True
        # No ChromaDB writes in dry_run mode - chunk stage should be skipped
