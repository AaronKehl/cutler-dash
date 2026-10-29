import csv, gzip, boto3, io
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient import discovery
import streamlit as st
import pandas as pd
from plotly import graph_objects as go

default_config = {
    'scrollZoom': True
}

@ st.cache_data
def read_idrive( key_prefix="idrive", bucket="flexivue", owner="chl", site="cutler", dtype="" ):
    idrive = boto3.client( 
        "s3",
        aws_access_key_id = st.secrets["creds"][key_prefix]["key"], 
        aws_secret_access_key = st.secrets["creds"][key_prefix]["secret"],
        endpoint_url = st.secrets["creds"][key_prefix]["endpoint"],
    )
    
    if owner == "":
        data = idrive.get_object( Bucket=bucket, Key=site+"/telemetry/"+site+"-master-"+dtype+".csv.gz" )
    else:
        if key_prefix == "grid":
            data = idrive.get_object( Bucket=bucket, Key="flexivue/"+owner+"/"+site+"/telemetry/"+site+"-master"+dtype+".csv.gz" )
        else:
            data = idrive.get_object( Bucket=bucket, Key=owner+"/"+site+"/telemetry/"+site+"-master"+dtype+".csv.gz" )
    contents = gzip.decompress( data['Body'].read() ).decode( 'iso8859_2' )
    return contents

def screen_data( variable, value ):
    # Add acceptable min/max for screening data based on var?
    try:
        if int( value ) != -9999: return True
    except: pass
    try: 
        if value == "0b0" or value == "0b1": return True
    except: pass
    try:
        if value == "0b00" or value == "0b01" \
            or value == "0b10" or value == "0b11":
            return True
    except: pass
    return False

def plot_chart( data, plot_var_1="", plot_var_2="" , open_date="", close_date=""):
    if open_date is None or open_date == "": open_date = datetime( 2020, 3, 9, 0, 0, 0)
    else: open_date = datetime( open_date.year, open_date.month, open_date.day, 0, 0, 0 )
    if close_date is None or close_date == "": close_date = datetime.now
    else: close_date = datetime( close_date.year, close_date.month, close_date.day, 23, 59, 59 )

    # var 1 set or var 2 set
    if (plot_var_1 and not plot_var_2) or (not plot_var_1 and plot_var_2):
        if plot_var_1: plot_var = plot_var_1
        if plot_var_2: plot_var = plot_var_2

        csvfile = io.StringIO( data )
        reader = csv.DictReader( csvfile, delimiter="," )
        var_names = reader.fieldnames
        x = []; y = []; row_pos = 0

        for row in reader:
            if row_pos == 0:
                x_units = row[ var_names[0] ] +" "+ row[ var_names[1] ]
                y_units = row[ plot_var ]
            else:
                try:    
                    timestamp = datetime.strptime( 
                        row[ var_names[0] ] +" "+ row[ var_names[1] ],
                        "%Y/%m/%d %H:%M:%S" 
                    )
                    if timestamp >= open_date and timestamp <= close_date:
                        try: y_val = float( row[ plot_var ] )
                        except: y_val = row[ plot_var ]
                        if screen_data( row[ plot_var ], y_val ):
                            x.append( timestamp )
                            y.append( y_val )
                except: pass
            row_pos += 1

        fig = go.Figure(
            data=[
                go.Scatter(
                    x=x,y=y,
                    mode='lines+markers',
                    name=f"{plot_var}"
                )
            ],
            layout=go.Layout(
                xaxis=dict( title=f"Datetime [UTC]" ),
                yaxis=dict( title=f"{plot_var} [{y_units}]"),
                margin=dict( t=0,b=0,l=0,r=0)
            )
        )
        st.plotly_chart(fig, config=default_config, height=500, width="stretch" )

    if plot_var_1 and plot_var_2:
        csvfile = io.StringIO( data )
        reader = csv.DictReader( csvfile, delimiter="," )
        var_names = reader.fieldnames
        x = []; y1 = []; y2 = []; row_pos = 0

        for row in reader:
            if row_pos == 0:
                x_units = row[ var_names[0] ] +" "+ row[ var_names[1] ]
                y1_units = row[ plot_var_1 ]
                y2_units = row[ plot_var_2 ]
            else:
                try:    
                    timestamp = datetime.strptime( 
                        row[ var_names[0] ] +" "+ row[ var_names[1] ],
                        "%Y/%m/%d %H:%M:%S" 
                    )
                    if timestamp >= open_date and timestamp <= close_date:
                        try: y1_val = float( row[ plot_var_1 ] )
                        except: y1_val = row[ plot_var_1 ]
                        try: y2_val = float( row[ plot_var_2 ] )
                        except: y2_val = row[ plot_var_2 ]
                        if screen_data( row[ plot_var_1 ], y1_val ) \
                            and screen_data( row[ plot_var_2 ], y2_val ):
                            x.append( timestamp )
                            y1.append( y1_val )
                            y2.append( y2_val )

                except: pass
            row_pos += 1

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x,y=y1,
                mode='lines+markers',
                name=f"{plot_var_1}"
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x,y=y2,
                mode='lines+markers',
                name=f"{plot_var_2}",
                yaxis="y2"
            )
        )
        fig.update_layout(
                xaxis=dict( title=f"Datetime [UTC]" ),
                yaxis=dict( title=f"{plot_var_1} [{y1_units}]"),
                yaxis2=dict( title=f"{plot_var_2} [{y2_units}]",anchor="x",overlaying="y",side="right",tickmode='sync'),
                margin=dict( t=0,b=0,l=0,r=0),
                hovermode="x unified",
                legend=dict( x=0.01, y=0.99, xanchor='left',yanchor='top',orientation='h')
        )
        
        st.plotly_chart(fig, config=default_config, height=500, width="stretch" )

@st.cache_data(ttl=600)  # Cache IAM lookups for 10 minutes to maintain speed
def check_user_iam_permission(email_to_check: str) -> bool:
    """
    Queries the GCP IAM API via a Service Account to see if the user has 
    access to the project.
    """
    try:
        # Load the service account credentials from st.secrets
        gcp_info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(gcp_info)
        
        # Build the Cloud Resource Manager API service
        service = discovery.build('cloudresourcemanager', 'v1', credentials=credentials)
        project_id = gcp_info["project_id"]
        
        # Fetch the complete IAM Policy map for the project
        policy = service.projects().getIamPolicy(resource=project_id, body={}).execute()
        bindings = policy.get('bindings', [])
        
        # Format the identity string Google IAM expects
        target_member = f"user:{email_to_check.lower()}"
        
        # Define what role grants access (e.g., any Project Viewer or higher)
        # You can change this to any specific role you want to enforce
        REQUIRED_ROLE = [
            "roles/owner",
            "roles/viewer",
            "rolex/editor",
            "roles/oauthconfig.viewer"
        ]
        
        for binding in bindings:
            if binding.get('role') in REQUIRED_ROLE:
                members = [m.lower() for m in binding.get('members', [])]
                if target_member in members:
                    return True
                    
        return False
    except Exception as e:
        st.error(f"Authorization Engine Error: Unable to query IAM system.")
        return False
    
if __name__ == "__main__":
    if not st.user.is_logged_in:
        if st.button("Log in with Google"):
            st.login("google")
        st.stop()

    user_email = st.user.get("email")
    if not check_user_iam_permission(user_email):
        st.error(f"⛔ Access Denied. The identity '{user_email}' does not possess the required IAM roles in Google Cloud.")
        if st.button("Log out and/or switch account"):
            st.logout()
        st.stop()
        
    params = st.query_params
    site_name = params["site"][0:1].upper() + params["site"][1:]

    # Set up the bones of the page
    st.set_page_config( page_title=site_name, page_icon="📈" )
    st.write("# " + site_name + " FlexiVue Z Level 📈")

    link_left, link_midl, link_midr, link_right = st.columns(4)
    link_left.page_link( "dashboard.py", label="Dashboard" )
    link_midl.page_link( "pages/telemetry.py", label="Telemetry", query_params=params )
    link_midr.page_link( "pages/images.py", label="Images", query_params=params )
    link_right.page_link( "pages/dems.py", label="DEMs", query_params=params)

    if params["dtype"] != "":
        # Grab z Level data from master file.
        data = read_idrive( params["key_prefix"], params["bucket"], params["owner"], params["site"], params["dtype"] )
        csvfile = io.StringIO( data )
        reader = csv.DictReader( csvfile, delimiter="," )
        var_names = reader.fieldnames

        # Set up options for graphing variables contained in the levels file by open/close dates
        top_left, top_right = st.columns( 2 )
        plot_var_1 = top_left.selectbox( "Select Variable 1", [""] + var_names )
        plot_var_2 = top_right.selectbox( "Select Variable 2", [""] + var_names )
        bot_left, bot_middle, bot_right = st.columns( 3, vertical_alignment = "bottom" )
        default_open = datetime.now() - timedelta( days = 7 )
        open_date = bot_left.date_input( "Begin Date", value = default_open )
        close_date = bot_middle.date_input( "End Date", value = "today" )
        if bot_right.button( "Plot Chart", use_container_width=True):
            plot_chart( data, plot_var_1, plot_var_2, open_date, close_date )

        # populate an image/description for the level page for a specific site
        st.image( "img/"+params["owner"]+"-"+params["site"]+"-"+params["dtype"]+".png", caption="Depiction of where level is determined." )
    else:
        st.write("## No additional telemetry file exists for this site, main telemetry file only." )
        
    #st.write( "You selected:", var_names )

    if st.button("Log out"):
        st.logout()
