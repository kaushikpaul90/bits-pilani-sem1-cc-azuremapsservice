import json
import azure.functions as func
import logging

from azure.core.credentials import AzureKeyCredential
from azure.maps.search import MapsSearchClient
from azure.core.exceptions import HttpResponseError
import requests

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="azureMapApi")
def azure_map_http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    req_body = req.get_json()
    location = req_body.get('location')
    from_location = req_body.get('from')
    to_location = req_body.get('to')
    # location = req.params.get('location')
    # from_location = req.params.get('from')
    # to_location = req.params.get('to')
    subscription_key = req.headers.get('subscription_key')

    if location:
        lat, lon = get_coordinates(subscription_key, location)
    
        if lat is None or lon is None:
            print("Location not found. Please try a different location.")
            return
        
        print("Fetching traffic flow data...")
        traffic_flow = get_traffic_flow(subscription_key, lat, lon, 5, "absolute", "KMPH")
        print(traffic_flow)
        
        print("Fetching traffic incident details...")
        traffic_incidents = get_traffic_incidents(subscription_key, lat, lon, lat + 0.1, lon + 0.1, 5)
        print(traffic_incidents)
        
        # Example route details from the given location to a nearby point
        print("Fetching route details...")
        route_details = get_route_details(subscription_key, lat, lon, lat + 0.1, lon + 0.1)
        print(route_details)

    if from_location and to_location:
        from_lat, from_lon = get_coordinates(subscription_key, from_location)
        to_lat, to_lon = get_coordinates(subscription_key, to_location)
    
        if from_lat is None or from_lon is None or to_lat is None or to_lon is None:
            print("Location not found. Please try a different location.")
            return
        
        print("Fetching traffic flow data...")
        traffic_flow = get_traffic_flow(subscription_key, from_lat, from_lon, 5, "absolute", "KMPH")
        print(traffic_flow)
        
        print("Fetching traffic incident details...")
        traffic_incidents = get_traffic_incidents(subscription_key, from_lat, from_lon, to_lat, to_lon, 5)
        print(traffic_incidents)
        
        # Example route details from the given location to a nearby point
        print("Fetching route details...")
        route_details = get_route_details(subscription_key, from_lat, from_lon, to_lat, to_lon)
        print(route_details)

    # Remove 'coordinates' key from traffic_flow if it exists
    if 'coordinates' in traffic_flow['flowSegmentData']:
        del traffic_flow['flowSegmentData']['coordinates']

    # Remove 'points' key from route_details if it exists
    for route in route_details['routes']:
        for leg in route['legs']:
            if 'points' in leg:
                del leg['points']

    # Combine the data into a single dictionary
    combined_data = {
        "traffic_flow": traffic_flow,
        "traffic_incidents": traffic_incidents,
        "route_details": route_details
    }

    # Convert the dictionary to a JSON string
    json_data = json.dumps(combined_data, indent=4)

    return func.HttpResponse(json_data)
    
# Function to get coordinates from location name using Azure Maps Geocoding API
def get_coordinates(subscription_key, location_name):
    url = f"https://atlas.microsoft.com/search/address/json?api-version=1.0&subscription-key={subscription_key}&query={location_name}"
    response = requests.get(url)
    data = response.json()
    if data['results']:
        position = data['results'][0]['position']
        return position['lat'], position['lon']
    else:
        return None, None

# Function to get traffic flow data
def get_traffic_flow(subscription_key, lat, lon, zoom, style, unit):
    url = f"https://atlas.microsoft.com/traffic/flow/segment/json?api-version=1.0&subscription-key={subscription_key}&query={lat},{lon}&zoom={zoom}&style={style}&unit={unit}"
    response = requests.get(url)
    return response.json()

# Function to get traffic incident details
def get_traffic_incidents(subscription_key, start_lat, start_lon, end_lat, end_lon, bounding_zoom):
    bounding_box = f"{start_lon},{start_lat},{end_lon},{end_lat}"
    # URL for the Traffic Incident Viewport endpoint
    viewport_url = "https://atlas.microsoft.com/traffic/incident/viewport/json?"

    # Parameters for the request
    params = {
        'api-version': '1.0',
        'boundingbox': bounding_box,
        'boundingzoom': bounding_zoom,
        'overviewbox': bounding_box,
        'overviewzoom': bounding_zoom,
        'subscription-key': subscription_key
    }

    # Make a request to the Traffic Incident Viewport endpoint
    response = requests.get(viewport_url, params=params)

    if response.status_code == 200:
        data = response.json()
        traffic_model_id = data['viewpResp']['trafficState']['@trafficModelId']
        print(f"Traffic Model ID: {traffic_model_id}")
    else:
        print(f"Error: {response.status_code}, {response.json()}")

    # URL for the Traffic Incident Detail endpoint
    incident_detail_url = "https://atlas.microsoft.com/traffic/incident/detail/json"

    # Parameters for the request
    params = {
        'api-version': '1.0',
        'style': 's1',
        'subscription-key': subscription_key,
        'boundingbox': bounding_box,
        'boundingZoom': bounding_zoom,
        'trafficmodelid': traffic_model_id
    }

    # Make a request to the Traffic Incident Detail endpoint
    response = requests.get(incident_detail_url, params=params)

    if response.status_code == 200:
        data = response.json()
        print(data)
    else:
        print(f"Error: {response.status_code}, {response.json()}")

    return response.json()

# Function to get route details
def get_route_details(subscription_key, start_lat, start_lon, end_lat, end_lon):
    url = f"https://atlas.microsoft.com/route/directions/json?api-version=1.0&subscription-key={subscription_key}&query={start_lat},{start_lon}:{end_lat},{end_lon}&travelMode=car"
    response = requests.get(url)
    return response.json()

def geocode(subscription_key, location):
    maps_search_client = MapsSearchClient(credential=AzureKeyCredential(subscription_key))
    try:
        result = maps_search_client.get_geocoding(query=location)
        return json.dumps(result)

    except HttpResponseError as exception:
        if exception.error is not None:
            print(f"Error Code: {exception.error.code}")
            print(f"Message: {exception.error.message}")
        return json.dumps("Error Code: {exception.error.code}" + " | " + f"Message: {exception.error.message}")