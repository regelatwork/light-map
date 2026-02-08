import svgelements

svg_content = """
<svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="10" width="80" height="80" stroke="red" stroke-width="2" fill="none" />
</svg>
"""

with open("debug.svg", "w") as f:
    f.write(svg_content)

svg = svgelements.SVG.parse("debug.svg")
matrix = svgelements.Matrix()
matrix.post_translate(1000, 1000)

for element in svg.elements():
    if isinstance(element, svgelements.Shape):
        path = svgelements.Path(element)
        print(f"Original transform: {path.transform}")
        
        transformed_path = path * matrix
        print(f"Transformed transform: {transformed_path.transform}")
        
        print("Iterating Transformed Segments:")
        for segment in transformed_path:
            print(segment)
            break
            
        print("Reified:")
        try:
            reified_path = svgelements.Path(transformed_path)
            reified_path.reify()
            for segment in reified_path:
                print(segment)
                break
        except Exception as e:
            print(f"Reify failed: {e}")
