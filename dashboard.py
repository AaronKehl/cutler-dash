import json, boto3
import streamlit as st

def read_idrive( key_prefix="idrive",bucket="flexivue", prefix="", dtype="" ):
    idrive = boto3.client( 
        "s3",
        aws_access_key_id = st.secrets["creds"][key_prefix]["key"], 
        aws_secret_access_key = st.secrets["creds"][key_prefix]["secret"],
        endpoint_url = st.secrets["creds"][key_prefix]["endpoint"],
    )

    data = idrive.get_object( Bucket=bucket, Key="st-sites.json" )
    nested_jsons = json.loads( data['Body'].read().decode() )

    return nested_jsons

def populate_page():
    nested_jsons = read_idrive()
    page_names = []
    for key,value in nested_jsons.items():
        page_names.append( key )

    rows = []
    row_data = []
    full_rows = int( len( page_names ) / 3 )
    part_row = int( len( page_names ) % 3 )
    for i in range( full_rows ): rows.append( st.columns( 3 ) )
    if part_row != 0: rows.append( st.columns( part_row, width=225) )
    for entry in rows: row_data = row_data + entry

    index = 0
    for col in row_data:
        
        key_prefix = nested_jsons[ page_names[index] ]["key_prefix"]
        bucket = nested_jsons[ page_names[index] ]["bucket"]
        owner = nested_jsons[ page_names[index] ]["owner"]
        site = nested_jsons[ page_names[index] ]["site"]
        dtype = nested_jsons[ page_names[index] ]["dtype"]

        unit = page_names[index]
        tile = col.container(height=185, vertical_alignment="top", horizontal_alignment="center" )
        tile.page_link( "pages/telemetry.py", label=page_names[index], width="stretch", query_params=nested_jsons[page_names[index]] )
        tile.image( "img/"+owner+"-"+site+".jpeg", width="stretch")
        index += 1


if __name__ == "__main__":
    if not st.user.is_logged_in:
        if st.button("Log in with Google", width='stretch'):
            st.login("google")
        st.stop()

    st.set_page_config( page_title="dashboard", page_icon="⚓" )
    st.write("# FlexiVue Dashboard ⚓")

    populate_page()

    if st.button("Log out"):
        st.logout()