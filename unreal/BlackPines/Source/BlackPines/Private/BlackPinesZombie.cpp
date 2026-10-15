#include "BlackPinesZombie.h"

#include "BlackPinesRoundDirector.h"
#include "BlackPinesZombieAIController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Net/UnrealNetwork.h"

ABlackPinesZombie::ABlackPinesZombie()
{
    PrimaryActorTick.bCanEverTick = false;
    bReplicates = true;
    SetReplicateMovement(true);

    AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
    AIControllerClass = ABlackPinesZombieAIController::StaticClass();

    GetCharacterMovement()->MaxWalkSpeed = 165.f;
    GetCharacterMovement()->bOrientRotationToMovement = true;
    bUseControllerRotationYaw = false;
}

void ABlackPinesZombie::BeginPlay()
{
    Super::BeginPlay();
    if (HasAuthority() && Health <= 0.f)
    {
        Health = FMath::Max(1.f, BaseHealth);
    }
}

void ABlackPinesZombie::InitializeForRound(
    int32 InRound,
    ABlackPinesRoundDirector* InDirector)
{
    if (!HasAuthority())
    {
        return;
    }

    RoundDirector = InDirector;
    const int32 RoundHealth = InDirector
        ? InDirector->ZombieHealth(InRound)
        : FMath::RoundToInt(BaseHealth);

    Health = static_cast<float>(FMath::Max(1, RoundHealth));
    bDead = false;
}

float ABlackPinesZombie::TakeDamage(
    float DamageAmount,
    FDamageEvent const& DamageEvent,
    AController* EventInstigator,
    AActor* DamageCauser)
{
    if (!HasAuthority() || bDead || DamageAmount <= 0.f)
    {
        return 0.f;
    }

    const float Applied = FMath::Min(Health, DamageAmount);
    Health = FMath::Max(0.f, Health - Applied);

    if (Health <= 0.f)
    {
        Die();
    }

    return Applied;
}

bool ABlackPinesZombie::TryMeleeAttack(AActor* Target)
{
    if (!HasAuthority() || bDead || !IsValid(Target))
    {
        return false;
    }

    const float DistSq = FVector::DistSquared(GetActorLocation(), Target->GetActorLocation());
    if (DistSq > FMath::Square(FMath::Max(1.f, AttackRange)))
    {
        return false;
    }

    const float Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
    if ((Now - LastAttackTime) < FMath::Max(0.05f, AttackCooldown))
    {
        return false;
    }

    LastAttackTime = Now;
    FDamageEvent DamageEvent;
    Target->TakeDamage(AttackDamage, DamageEvent, GetController(), this);
    return true;
}

void ABlackPinesZombie::Die()
{
    if (bDead)
    {
        return;
    }

    bDead = true;
    GetCharacterMovement()->StopMovementImmediately();
    GetCharacterMovement()->DisableMovement();
    SetActorEnableCollision(false);

    if (RoundDirector)
    {
        RoundDirector->RegisterZombieDeath();
    }

    SetLifeSpan(1.25f);
}

void ABlackPinesZombie::OnRep_Health()
{
    if (Health <= 0.f)
    {
        bDead = true;
    }
}

void ABlackPinesZombie::GetLifetimeReplicatedProps(
    TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABlackPinesZombie, Health);
    DOREPLIFETIME(ABlackPinesZombie, bDead);
}
