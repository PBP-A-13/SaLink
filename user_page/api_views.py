from django.contrib.auth import authenticate

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    parser_classes,
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response

from .serializers import RegisterSerializer, UserProfileSerializer


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def register_api(request):
    serializer = RegisterSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.save()
        return Response(
            {
                'message': 'Registrasi berhasil.',
                'username': user.username,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_api(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response(
            {'error': 'Username dan password wajib diisi.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(
        request,
        username=username,
        password=password,
    )

    if user is None:
        return Response(
            {'error': 'Username atau password salah.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)

    return Response(
        {
            'message': 'Login berhasil.',
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def logout_api(request):
    request.user.auth_token.delete()

    return Response(
        {'message': 'Logout berhasil.'},
        status=status.HTTP_200_OK,
    )


@api_view(['GET', 'PATCH', 'PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def profile_api(request):
    user = request.user

    if request.method == 'GET':
        serializer = UserProfileSerializer(user)
        return Response(serializer.data)

    serializer = UserProfileSerializer(
        user,
        data=request.data,
        partial=(request.method == 'PATCH'),
    )

    if serializer.is_valid():
        serializer.save()
        return Response(
            {
                'message': 'Profil berhasil diperbarui.',
                'profile': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )
