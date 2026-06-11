from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start_location = serializers.CharField(max_length=255, trim_whitespace=True)
    finish_location = serializers.CharField(max_length=255, trim_whitespace=True)
