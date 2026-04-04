from domain.services.orchestrator import CalculationOrchestrator
from domain.entities.definitions import CalculationRequest

orchestrator = CalculationOrchestrator()
inputs = {f"var{i}": float(i) for i in range(10)}
request = CalculationRequest(inputs=inputs)
result = orchestrator.orchestrate(request)
print("Status:", result.status)
print("Messages:", result.messages)