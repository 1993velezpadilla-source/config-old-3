#include "BlackPinesZombieAIController.h"

#include "BlackPinesZombie.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"

ABlackPinesZombieAIController::ABlackPinesZombieAIController()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = 0.20f;
    bSetControlRotationFromPawnOrientation = true;
}

void ABlackPinesZombieAIController::OnPossess(APawn* InPawn)
{
    Super::OnPossess(InPawn);
    CurrentTarget.Reset();
}

APawn* ABlackPinesZombieAIController::FindNearestPlayerPawn() const
{
    const UWorld* World = GetWorld();
    const APawn* ControlledPawn = GetPawn();
    if (!World || !ControlledPawn)
    {
        return nullptr;
    }

    APawn* Best = nullptr;
    double BestDistSq = TNumericLimits<double>::Max();

    for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
    {
        const APlayerController* PC = It->Get();
        APawn* Candidate = PC ? PC->GetPawn() : nullptr;
        if (!IsValid(Candidate))
        {
            continue;
        }

        const double DistSq = FVector::DistSquared(
            ControlledPawn->GetActorLocation(),
            Candidate->GetActorLocation());

        if (DistSq < BestDistSq)
        {
            BestDistSq = DistSq;
            Best = Candidate;
        }
    }

    return Best;
}

void ABlackPinesZombieAIController::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);

    ABlackPinesZombie* Zombie = Cast<ABlackPinesZombie>(GetPawn());
    if (!Zombie || Zombie->IsDead())
    {
        StopMovement();
        return;
    }

    if (!CurrentTarget.IsValid())
    {
        CurrentTarget = FindNearestPlayerPawn();
    }

    APawn* Target = CurrentTarget.Get();
    if (!Target)
    {
        CurrentTarget = FindNearestPlayerPawn();
        Target = CurrentTarget.Get();
    }

    if (!Target)
    {
        StopMovement();
        return;
    }

    const float AcceptanceRadius = FMath::Max(25.f, Zombie->AttackRange * 0.70f);
    MoveToActor(Target, AcceptanceRadius, true, true, true, nullptr, true);
    Zombie->TryMeleeAttack(Target);
}
