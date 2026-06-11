import json

import requests
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .serializers import RouteRequestSerializer
from .services.geocoding import GeocodingError
from .services.route_planner import plan_route
from .services.routing import RoutingError


class RoutePlanThrottle(AnonRateThrottle):
    scope = "route-plan"


class RoutePlanView(APIView):
    throttle_classes = [RoutePlanThrottle]

    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = plan_route(**serializer.validated_data)
        except GeocodingError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RoutingError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except requests.RequestException:
            return Response(
                {"error": "A required external mapping service is currently unavailable. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(result)


def route_map_view(request):
    start_location = request.GET.get("start_location", "")
    finish_location = request.GET.get("finish_location", "")

    context = {"start_location": start_location, "finish_location": finish_location}

    if start_location and finish_location:
        try:
            result = plan_route(start_location, finish_location)
            context["route_data"] = json.dumps(result)
            context["result"] = result
        except (GeocodingError, RoutingError, requests.RequestException) as exc:
            context["error"] = str(exc)

    return render(request, "fuelroute/map.html", context)
