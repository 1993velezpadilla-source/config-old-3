#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "BlackPinesZombieAIController.generated.h"

UCLASS()
class BLACKPINES_API ABlackPinesZombieAIController : public AAIController
{
    GENERATED_BODY()

public:
    ABlackPinesZombieAIController();

protected:
    virtual void OnPossess(APawn* InPawn) override;
    virtual void Tick(float DeltaSeconds) override;

private:
    APawn* FindNearestPlayerPawn() const;

    TWeakObjectPtr<APawn> CurrentTarget;
};
