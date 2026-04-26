extends Node

@onready var visuals: Node3D = $"../Visuals"
@onready var base_link: Node3D = $"../Visuals/base_link"
@onready var wheel_left_link: Node3D = $"../Visuals/base_link/wheel_left_link"
@onready var wheel_right_link: Node3D = $"../Visuals/base_link/wheel_right_link"

var _left_origin: Transform3D
var _right_origin: Transform3D

func _ready() -> void:
    _left_origin = wheel_left_link.transform
    _right_origin = wheel_right_link.transform

func apply_base_pose(position: Vector3, rotation_quat: Quaternion) -> void:
    visuals.global_position = position
    visuals.global_transform.basis = Basis(rotation_quat)

func apply_joint_state(left_angle: float, right_angle: float) -> void:
    wheel_left_link.transform = _left_origin * Transform3D(Basis(Vector3(0, 0, 1), left_angle), Vector3.ZERO)
    wheel_right_link.transform = _right_origin * Transform3D(Basis(Vector3(0, 0, 1), right_angle), Vector3.ZERO)
