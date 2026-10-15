#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "BlackPinesGameMode.generated.h"

class ABlackPinesRoundDirector;

UCLASS()
class BLACKPINES_API ABlackPinesGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    ABlackPinesGameMode();

    virtual void StartPlay() override;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="BlackPines|Rounds")
    TSubclassOf<ABlackPinesRoundDirector> RoundDirectorClass;
};
