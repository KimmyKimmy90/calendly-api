#!/usr/bin/env python3
"""
Simple Calendly API Proxy Server
Handles Calendly API calls to avoid CORS issues in the browser
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Dayton's Calendly Configuration
CALENDLY_CONFIG = {
    'token': 'eyJraWQiOiIxY2UxZTEzNjE3ZGNmNzY2YjNjZWJjY2Y4ZGM1YmFmYThhNjVlNjg0MDIzZjdjMzJiZTgzNDliMjM4MDEzNWI0IiwidHlwIjoiUEFUIiwiYWxnIjoiRVMyNTYifQ.eyJpc3MiOiJodHRwczovL2F1dGguY2FsZW5kbHkuY29tIiwiaWF0IjoxNzQ5NjE1MjUwLCJqdGkiOiIyMzFjYmNkZC02MmQ2LTRmMWEtYTZlYS1lZTBkZDQ1MjliYmYiLCJ1c2VyX3V1aWQiOiI5MTViNGI1NC1mMDdjLTRhMTItODEwYy01N2UzOTgyYWU1OTgifQ.VjXWxPYreWFN1Xkr8KVTbAlU8slaodyOYbO_aUeYuaZ6lSftUoCXbrBTIks1QVZHnvlfgQvBeBKuXvw7vHIKrg',
    'event_type_uri': 'https://api.calendly.com/event_types/aa4d24d2-1db9-4679-b296-59fc3c5e8970',
    'user_uri': 'https://api.calendly.com/users/915b4b54-f07c-4a12-810c-57e3982ae598'
}

# API Headers for Calendly
headers = {
    'Authorization': f'Bearer {CALENDLY_CONFIG["token"]}',
    'Content-Type': 'application/json'
}

@app.route('/')
def index():
    return jsonify({
        'message': 'Calendly API Proxy Server for Schofield Solutions',
        'status': 'running',
        'endpoints': [
            '/api/availability',
            '/api/book',
            '/api/health'
        ]
    })

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/availability')
def get_availability():
    """Get available time slots from Calendly"""
    try:
        # Get date range from query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str:
            start_date = datetime.now() + timedelta(days=1)
        else:
            start_date = datetime.fromisoformat(start_date_str)
            
        if not end_date_str:
            # Calendly API only allows 7 days max
            end_date = start_date + timedelta(days=6)
        else:
            end_date = datetime.fromisoformat(end_date_str)
            # Ensure we don't exceed 7 days
            if (end_date - start_date).days > 6:
                end_date = start_date + timedelta(days=6)
        
        # Call Calendly API for availability
        url = "https://api.calendly.com/event_type_available_times"
        params = {
            'event_type': CALENDLY_CONFIG['event_type_uri'],
            'start_time': start_date.strftime('%Y-%m-%dT09:00:00.000Z'),
            'end_time': end_date.strftime('%Y-%m-%dT23:59:59.999Z')
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            availability_data = response.json()
            
            # Process and organize the data
            available_slots = []
            for slot in availability_data.get('collection', []):
                slot_time = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00'))
                available_slots.append({
                    'start_time': slot['start_time'],
                    'formatted_time': slot_time.strftime('%A, %B %d at %I:%M %p'),
                    'date': slot_time.strftime('%Y-%m-%d'),
                    'time': slot_time.strftime('%I:%M %p')
                })
            
            # Group by date
            dates_with_slots = {}
            for slot in available_slots:
                date = slot['date']
                if date not in dates_with_slots:
                    dates_with_slots[date] = []
                dates_with_slots[date].append(slot)
            
            return jsonify({
                'success': True,
                'available_dates': list(dates_with_slots.keys()),
                'slots_by_date': dates_with_slots,
                'total_slots': len(available_slots)
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Calendly API error: {response.status_code}',
                'details': response.text
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/book', methods=['POST'])
def create_booking():
    """Create a new Calendly booking"""
    try:
        booking_data = request.get_json()
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'email', 'start_time']
        for field in required_fields:
            if field not in booking_data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Prepare Calendly booking request
        calendly_booking_data = {
            'event_type': CALENDLY_CONFIG['event_type_uri'],
            'start_time': booking_data['start_time'],
            'invitee': {
                'name': f"{booking_data['first_name']} {booking_data['last_name']}",
                'email': booking_data['email']
            }
        }
        
        # Add phone number if provided
        if 'phone' in booking_data:
            calendly_booking_data['invitee']['phone_number'] = booking_data['phone']
        
        # Create the booking via Calendly API
        url = "https://api.calendly.com/scheduled_events"
        response = requests.post(url, headers=headers, json=calendly_booking_data)
        
        if response.status_code == 201:
            booking_result = response.json()
            
            return jsonify({
                'success': True,
                'booking_id': booking_result['resource']['uri'],
                'message': 'Booking created successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Calendly booking error: {response.status_code}',
                'details': response.text
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/test')
def test_calendly_connection():
    """Test the Calendly API connection"""
    try:
        # Test user info endpoint
        url = "https://api.calendly.com/users/me"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            return jsonify({
                'success': True,
                'message': 'Calendly API connection successful',
                'user': user_data['resource']['name'],
                'email': user_data['resource']['email']
            })
        else:
            return jsonify({
                'success': False,
                'error': f'API test failed: {response.status_code}',
                'details': response.text
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)

