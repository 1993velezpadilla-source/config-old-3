#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "BlackPinesRoundDirector.generated.h"

class ABlackPinesZombie;

UCLASS(Blueprintable)
class BLACKPINES_API ABlackPinesRoundDirector : public AActor
{
    GENERATED_BODY()

public:
    ABlackPinesRoundDirector();

    UFUNCTION(BlueprintCallable, Category="BlackPines|Rounds")
    bool BeginNextRound();

    UFUNCTION(BlueprintCallable, Category="BlackPines|Rounds")
    bool RegisterZombieSpawn();

    UFUNCTION(BlueprintCallable, Category="BlackPines|Rounds")
    void RegisterZombieDeath();

    UFUNCTION(BlueprintPure, Category="BlackPines|Rounds")
    int32 WavePopulation(int32 Wave, int32 Players) const;

    UFUNCTION(BlueprintPure, Category="BlackPines|Rounds")
    int32 ZombieHealth(int32 Wave) const;

    UFUNCTION(BlueprintCallable, Category="BlackPines|Rounds")
    void RefreshSpawnPoints();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="BlackPines|Rounds")
    int32 CurrentRound = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="BlackPines|Rounds")
    int32 RoundTotal = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="BlackPines|Rounds")
    int32 SpawnedThisRound = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="BlackPines|Rounds")
    int32 AliveCount = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Android")
    int32 MaxAlive = 24;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Android")
    int32 MaxSoloWave = 144;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Android")
    int32 MaxHealth = 250000;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Coop")
    int32 PlayerCount = 1;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Spawning")
    TSubclassOf<ABlackPinesZombie> ZombieClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Spawning")
    FName SpawnPointTag = TEXT("ZombieSpawn");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Spawning")
    float SpawnInterval = 0.80f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="BlackPines|Spawning")
    float InterRoundDelay = 5.0f;

protected:
    virtual void BeginPlay() override;

private:
    void SpawnTick();
    bool SpawnOneZombie();
    void BeginNextRoundAfterDelay();

    UPROPERTY(Transient)
    TArray<TObjectPtr<AActor>> SpawnPoints;

    int32 SpawnCursor = 0;
    FTimerHandle SpawnTimerHandle;
    FTimerHandle NextRoundTimerHandle;
};
