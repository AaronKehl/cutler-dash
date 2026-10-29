
import streamlit as st
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient import discovery
import boto3

def adjust_params( params, tif_file ):
    tif_file = tif_file[:tif_file.find("DEPTH")] + "tif.gz"
    params.update( { "tif_file":tif_file } )
    return params

def read_idrive( open_date="", close_date="", key_prefix="idrive", bucket="flexivue", owner="chl", site="cutler", dtype="" ):
    # fix date range to search
    if open_date is None or open_date == "": open_date = datetime( 2020, 3, 9, 0, 0, 0)
    else: open_date = datetime( open_date.year, open_date.month, open_date.day, 0, 0, 0 )
    if close_date is None or close_date == "": close_date = datetime.now
    else: close_date = datetime( close_date.year, close_date.month, close_date.day, 23, 59, 59 )

    # generate client session to cloud server
    idrive = boto3.client( 
        "s3",
        aws_access_key_id = st.secrets["creds"][key_prefix]["key"], 
        aws_secret_access_key = st.secrets["creds"][key_prefix]["secret"],
        endpoint_url = st.secrets["creds"][key_prefix]["endpoint"],
    )

    # grab photo names from bucket, but parse down to between open/close dates first 1000 files.
    image_show = []
    msg_printed = False
    if owner == "": prefix = site + "/dems/"
    else: 
        if key_prefix == "grid":
            prefix = "flexivue/" + owner + "/" + site + "/dems/"
        else:
            prefix = owner + "/" + site + "/dems/"
    images = idrive.list_objects_v2( Bucket=bucket, Prefix=prefix)
    for image in images["Contents"]:
        try:
            filename = image["Key"].replace( prefix, "" )
            timestamp = datetime.strptime( filename[:filename.find(".")], '%Y%m%d-%H%M-%S' )
            if timestamp >= open_date and timestamp <= close_date and ".png" in filename: 
                if minmax_color:
                    if "IND" in filename: image_show.append( filename )
                if barearth_color:
                    if "ABS" in filename: image_show.append( filename )
                if not barearth_color and not minmax_color:
                    if not msg_printed:
                        st.caption( "You did not select a color mapping preference, defaulting to show colored by reference to bare earth.", text_alignment='center' )
                        msg_printed = True
                    if "ABS" in filename: image_show.append( filename )

                #print( filename )
        except: pass
            #idrive.delete_object( Bucket="flexivue", Key="/chl/cutler/photos/"+"", IfMatchSize=0 )
            #print( image[ "ETag" ] )
    
    # loop through listings if > 1000 files
    while images['IsTruncated']:
        images = idrive.list_objects_v2( 
                        Bucket=bucket, 
                        Prefix=prefix, 
                        ContinuationToken=images['NextContinuationToken'] 
                    )
        for image in images["Contents"]:
            try:
                filename = image["Key"].replace( prefix, "" )
                timestamp = datetime.strptime( filename[:filename.find(".")], '%Y%m%d-%H%M-%S' )
                if timestamp >= open_date and timestamp <= close_date and ".png" in filename: 
                    if minmax_color:
                        if "IND" in filename: image_show.append( filename )
                    if barearth_color:
                        if "ABS" in filename: image_show.append( filename )
                    if not barearth_color and not minmax_color:
                        if not msg_printed:
                            st.caption( "You did not select a color mapping preference, defaulting to show colored by reference to bare earth.", text_alignment='center' )
                            msg_printed = True
                        if "ABS" in filename: image_show.append( filename )
                    #print( filename )
            except: pass

    rows = []
    row_data = []
    full_rows = int( len( image_show ) / 3 )
    part_row = int( len( image_show ) % 3 )
    for i in range( full_rows ): rows.append( st.columns( 3 ) )
    if part_row != 0: rows.append( st.columns( part_row ) )
    for entry in rows: row_data = row_data + entry

    # here is where we grab the file contents to display on the page
    index = 0
    for col in row_data:
        tile = col.container(height=185, vertical_alignment="top",horizontal_alignment="center", gap="xxsmall")
        data = idrive.get_object( Bucket=bucket, Key=prefix+image_show[index] )
        image_file = data['Body'].read()
        image_name = image_show[index] 
        caption = image_name[:image_name.find(".")]
        tile.page_link( "pages/dem_plot.py", label=caption, query_params=adjust_params( params, image_name ) )
        tile.image( image_file )
        index += 1

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
        if st.button("Log in with Google", width='stretch'):
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
    
    st.set_page_config( page_title=site_name, page_icon="⛰" )
    st.write("# " + site_name + " FlexiVue DEMs ⛰")

    link_left, link_midl, link_midr, link_right = st.columns( 4 )
    link_left.page_link( "dashboard.py", label="Dashboard" )
    link_midl.page_link( "pages/telemetry.py" , label="Telemetry", query_params=params )
    link_midr.page_link( "pages/images.py", label="Images", query_params=params  )
    link_right.page_link( "pages/levels.py", label="Z Level", query_params=params )

    bot_left, bot_middle, bot_right = st.columns( 3, vertical_alignment = "bottom" )
    default_open = datetime.now() - timedelta( days = 7 )
    open_date = bot_left.date_input( "Begin Date", value = default_open )
    close_date = bot_middle.date_input( "End Date", value = "today" )

    # Radio buttons for which type we want to view...
    tgl_left, tgl_right = st.columns( 2 )
    minmax_color = tgl_left.toggle( "Show Colored by Min/Max of Individual Scan" )
    barearth_color = tgl_right.toggle( "Show Colored by Reference to Bare Earth" )
    
    st.caption( "Click image title to plot the raster on a chart.", text_alignment='center' )

    if bot_right.button( "Show Images", use_container_width=True ):
        read_idrive( 
            open_date, 
            close_date, 
            params["key_prefix"], 
            params["bucket"], 
            params["owner"], 
            params["site"], 
            params["dtype"] 
        )

    if st.button("Log out"):
        st.logout()
