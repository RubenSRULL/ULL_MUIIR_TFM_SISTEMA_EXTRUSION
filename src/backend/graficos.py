def figura_lineas(titulo, x_label, y_label, series):
    return {
        "data": [
            {
                "x": x,
                "y": y,
                "type": "scatter",
                "mode": "lines+markers",
                "name": nombre,
            }
            for nombre, x, y in series
        ],
        "layout": {
            "title": {"text": titulo, "font": {"color": "black", "size": 20}},
            "xaxis": {"title": {"text": x_label, "font": {"color": "black"}}, "automargin": True},
            "yaxis": {"title": {"text": y_label, "font": {"color": "black"}}, "automargin": True},
            "template": "plotly_white",
            "margin": {"t": 80, "l": 80, "r": 40, "b": 80},
            "paper_bgcolor": "white",
            "plot_bgcolor": "#f9f9f9",
        },
    }
