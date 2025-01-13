from shiny import App, render, ui, reactive
from jinja2 import Template
import folium

app_ui = ui.page_fluid(
    ui.h1("Folium Map that returns Coordinates of clicked spot"),
    ui.output_code("result"),
    ui.div(
        ui.output_ui("map"),
        style="height: 600px; width: 100%;"
    )
)

def server(input, output, session):
    # Initialize reactive value for coordinates
    clicked_coords = reactive.Value({'lat': None, 'lng': None})
   
    @output
    @render.ui
    def map():
        m = folium.Map(location=[-1.9403, 29.8739], zoom_start=8) 
        map_name = m.get_name()
        
        # attach a click event handler which captures the coordinates of
        # the click location and sends them to the shiny, updating clicked_coords
        code = """
        {% macro script(this,kwargs) %}
          function getLatLng(e){
            var lat = e.latlng.lat.toFixed(6),
                lng = e.latlng.lng.toFixed(6);
            parent.Shiny.setInputValue('clicked_coords', [lat, lng], {priority: 'event'});
           }; """ +  map_name + ".on('click', getLatLng){% endmacro %}"
           
        el = folium.MacroElement().add_to(m)
        el._template = Template(code)
        
        return ui.HTML(m._repr_html_())
    
    # processing the coordinates, e.g. rendering them
    @render.code
    @reactive.event(input.clicked_coords)
    def result():
        return (
            f"""
            Coordinates of click location: \n
            Latitude: {input.clicked_coords()[0]} \n
            Longitude: {input.clicked_coords()[1]}"""
        )

app = App(app_ui, server)