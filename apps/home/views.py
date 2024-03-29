# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import os
from datetime import timedelta
from django import template
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.template import loader
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_exempt
from .models import Room, Booking


def send_mail_to_id(id, subject, message):
    user = User.objects.get(id=id)
    user_email = user.email
    if user_email != "":
        send_mail(
            subject,
            message,
            None,
            [user_email],
            fail_silently=False,
        )


@login_required(login_url="/login/")
def index(request):
    context = {'segment': 'index'}
    context['segment'] = 'booking.html'
    html_template = loader.get_template('home/booking.html')
    return HttpResponse(html_template.render(context, request))


@login_required(login_url="/login/")
def pages(request):
    context = {}
    # All resource paths end in .html.
    # Pick out the html file name from the url. And load that template.
    # Todo: change to load only selected files.
    try:

        load_template = request.path.split('/')[-1]

        if load_template == 'admin':
            return HttpResponseRedirect(reverse('admin:index'))
        context['segment'] = load_template

        html_template = loader.get_template('home/' + load_template)
        return HttpResponse(html_template.render(context, request))

    except template.TemplateDoesNotExist:

        html_template = loader.get_template('home/page-404.html')
        return HttpResponse(html_template.render(context, request))

    except:
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render(context, request))


@csrf_exempt
def api(request, name, id=None):
    if name == 'all':
        return JsonResponse({
            'rooms': list(Room.objects.values()),
            'bookings': list(Booking.objects.filter(datetime_start__gte=timezone.now()-timedelta(days=2)).values()),
            'users': list(get_user_model().objects.all().values('id', 'username'))
        }, safe=False)
    if name == 'rooms':
        if id is None:
            return JsonResponse({
                'rooms': list(Room.objects.values())
            }, safe=False)

        else:
            # get all users

            users = list(
                get_user_model().objects.all().values('id', 'username'))
            room = list(Room.objects.filter(room_id=id).values())[0]
            booking = list(Booking.objects.select_related('booking_user_id').filter(
                booking_room_id=id, datetime_start__gte=timezone.now(), datetime_end__lte=timezone.now()+timedelta(days=28)).values())
            return JsonResponse({
                'room': room,
                'booking': booking,
                'users': users
            }, safe=False)

    if name == 'bookings':        
        if request.user.is_anonymous:
            telegram_id = request.headers.get('TG-ID')
            if telegram_id is not None:
                user = get_user_model().objects.filter(first_name=telegram_id).values('id')
                if user:
                    current_user_id = user[0]['id']                      
                else:
                    raise PermissionDenied()
            else:
                raise PermissionDenied()
        else:
            current_user_id = request.user.id

        if request.method == 'POST':
            data = request.POST
            room_name = 'UTS' if data['room_id']==1 else 'BIT'

            # print(current_user)

            # delete overlapping bookings if is admin
            if request.user.is_superuser:
                if request.user.username == "bitadmin":
                    bookings = Booking.objects.filter(                      
                        booking_room_id=data['room_id'],
                        datetime_start__lte=data['datetime_end'],
                        datetime_end__gte=data['datetime_start'])
                else:
                    bookings = Booking.objects.filter(    
                        datetime_start__lte=data['datetime_end'],
                        datetime_end__gte=data['datetime_start'])
                    bookings = bookings.filter(~Q(booking_user_id=2))
                    
                # if booking gets cancelled, email user
                # email each user once only for each block
                user_list = set()
                for booking in list(bookings):
                    user_id = getattr(booking, 'booking_user_id')
                    user_list.add(user_id)

                for id in user_list:
                    send_mail_to_id(
                        id,
                        "Bookings has been cancelled",
                        f"Hello,\n\nThe owner of {room_name} has blocked the room from {data['datetime_start']} to {data['datetime_end']}. All bookings within this period has been cancelled. Sorry for the inconvenience.\n\nCheers,\nTraining Booking System"
                    ) 

                bookings.delete()
                
            elif data['room_id'] == '2':
                # if BIT is booked, notify bitadmin
                send_mail_to_id(
                    2,
                    f"BIT booking has been made on {data['datetime_start'].split()[0]}",
                    f"Hello,\n\n{request.user.username.upper()} has booked BIT scenario {data['scenario']} on {data['datetime_start'].split()[0]}.\n\nCheers,\nTraining Booking System"
                )
            Booking.objects.create(datetime_start=data['datetime_start'], datetime_end=data['datetime_end'],
                                   booking_room_id=data['room_id'], booking_user_id=current_user_id, scenario=data['scenario'], pax=data['pax'])
            return JsonResponse({'status': 'success'}, safe=False)
        if request.method == 'GET':
            if id is None:
                return JsonResponse(list(Booking.objects.filter(booking_user_id=current_user_id, datetime_start__gte=timezone.now()-timedelta(days=2)).order_by('datetime_start').values()), safe=False)
        if request.method == 'DELETE':
            if id is not None:
                Booking.objects.filter(
                    booking_id=id, booking_user_id=current_user_id).delete()
                return JsonResponse({'status': 'success'}, safe=False)
    return JsonResponse({'name': name})


def get_blocked_bookings(request, start_date, start_time, end_date, end_time, room_id):
    bookings = Booking.objects.filter(
        date__gte=start_date, date__lte=end_date, booking_room_id=room_id)
    return JsonResponse(list(bookings.values()), safe=False)
