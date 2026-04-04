import pytest

from domain.entities.definitions import CalculationRequest, CalculationResult
from domain.entities.enums import CalculationStatus
from domain.services.orchestrator import CalculationOrchestrator, PremiumPolicyService


class TestPremiumPolicyService:
    """Test cases for PremiumPolicyService."""

    def test_allow_normal_request(self):
        policy = PremiumPolicyService()
        request = CalculationRequest(inputs={"lambda_": 2.0, "mu": 3.0})
        result = policy.check_premium(request)

    def test_block_exploration_request(self):
        policy = PremiumPolicyService()
        # Simulate many filled fields
        inputs = {f"var{i}": i for i in range(10)}
        request = CalculationRequest(inputs=inputs)
        result = policy.check_premium(request)
        assert result.allowed is False
        assert "Premium feature" in result.message


class TestCalculationOrchestrator:
    """Test cases for CalculationOrchestrator."""

    @pytest.fixture
    def orchestrator(self):
        return CalculationOrchestrator()

    def test_orchestrate_successful_calculation(self, orchestrator):
        # This would need mock services, simplified for now
        request = CalculationRequest(inputs={"lambda_": 2.0})
        result = orchestrator.orchestrate(request)
        # Assert basic structure
        assert isinstance(result, CalculationResult)
        assert "steps" in dir(result)

    def test_orchestrate_premium_block(self, orchestrator):
        # Create request that triggers premium block
        inputs = {f"var{i}": float(i) for i in range(10)}
        request = CalculationRequest(inputs=inputs)
        result = orchestrator.orchestrate(request)
        print("Messages:", result.messages)
        assert result.status == CalculationStatus.FAILED
        assert any("Premium feature" in msg for msg in result.messages)