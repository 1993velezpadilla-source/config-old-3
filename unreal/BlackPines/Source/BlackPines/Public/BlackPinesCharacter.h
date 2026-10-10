#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "BlackPinesCharacter.generated.h"
class UCameraComponent;
UCLASS()
class BLACKPINES_API ABlackPinesCharacter : public ACharacter
{
    GENERATED_BODY()
public:
    ABlackPinesCharacter();
protected:
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;
    void MoveForward(float Value);
    void MoveRight(float Value);
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="BlackPines|Camera")
    TObjectPtr<UCameraComponent> FPSCamera;
};
