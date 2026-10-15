#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "BlackPinesZombie.generated.h"

class ABlackPinesRoundDirector;
struct FLifetimeProperty;

UCLASS(Blueprintable)
class BLACKPINES_API ABlackPinesZombie : public ACharacter
{
    GENERATED_BODY()

public:
    ABlackPinesZombie();

    virtual float TakeDamage(
        float DamageAmount,
        struct FDamageEvent const& DamageEvent,
        class AController* EventInstigator,
        AActor* DamageCauser) override;

    virtual void GetLifetimeReplicatedProps(
        TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    UFUNCTION(BlueprintCallable, Category="BlackPines|Zombie")
    void InitializeForRound(int32 InRound, ABlackPinesRoundDirector* InDirector);

    UFUNCTION(BlueprintCallable, Category="BlackPines|Zombie")
    bool TryMeleeAttack(AActor* Target);

    UFUNCTION(BlueprintPure, Category="BlackPines|Zombie")
    bool IsDead() const { return bDead; }

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Zombie")
    float BaseHealth = 150.f;

    UPROPERTY(ReplicatedUsing=OnRep_Health, VisibleAnywhere, BlueprintReadOnly, Category="BlackPines|Zombie")
    float Health = 150.f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Zombie")
    float AttackDamage = 50.f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Zombie")
    float AttackRange = 125.f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Zombie")
    float AttackCooldown = 1.0f;

protected:
    virtual void BeginPlay() override;

    UFUNCTION()
    void OnRep_Health();

    void Die();

    UPROPERTY()
    TObjectPtr<ABlackPinesRoundDirector> RoundDirector;

    UPROPERTY(Replicated)
    bool bDead = false;

    float LastAttackTime = -1000.f;
};
