class UserProfile {
  final String id;
  final String email;
  final String name;
  final String? phone;
  final DateTime createdAt;

  UserProfile({
    required this.id,
    required this.email,
    required this.name,
    this.phone,
    required this.createdAt,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) => UserProfile(
        id: json['id'] as String,
        email: json['email'] as String,
        name: json['name'] as String,
        phone: json['phone'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
