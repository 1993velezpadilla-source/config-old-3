extends CharacterBody3D

var points: int = 1200
var spend_attempts: int = 0

func spend_points(price: int) -> bool:
	spend_attempts += 1
	if points < price:
		return false
	points -= price
	return true
