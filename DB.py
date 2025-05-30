import open3d as o3d
import numpy as np
import matplotlib.pyplot as plt

# ---------- CONFIGURE PARAMETERS ----------
pcd_path = r"C:/Users/Sowmya/OneDrive/Desktop/SHARMA/ImageToStl.com_SS2.pcd"
eps = 15                     # DBSCAN distance threshold in mm
min_points = 20               # Minimum points per cluster
xy_thresh = 50                # XY distance for vertical merge (mm)
z_gap_thresh = 100            # Max vertical gap for merging (mm)
min_cluster_size = 500        # Ignore clusters smaller than this

# Additional noise reduction parameters
outlier_nb_neighbors = 30     # Increased for better noise removal
outlier_std_ratio = 1.5       # Increased for stricter noise removal

# OBJECT FILTERING - Specify which objects to REMOVE/FILTER OUT
objects_to_remove = [1, 2, 4, 5, 6, 7, 9, 10, 11, 14]  # List of object numbers to exclude (added 7 to remove the green object)

# ---------- LOAD AND CLEAN POINT CLOUD ----------
print("Loading point cloud...")
pcd = o3d.io.read_point_cloud(pcd_path)
print(f"Original point cloud has {len(pcd.points)} points")

print("Removing statistical outliers...")
pcd, outlier_indices = pcd.remove_statistical_outlier(
    nb_neighbors=outlier_nb_neighbors, 
    std_ratio=outlier_std_ratio
)
print(f"After outlier removal: {len(pcd.points)} points (removed {len(outlier_indices)} outliers)")

# Additional radius outlier removal for better noise reduction
print("Applying radius-based outlier removal...")
pcd, radius_outlier_indices = pcd.remove_radius_outlier(nb_points=10, radius=20.0)
print(f"After radius outlier removal: {len(pcd.points)} points (removed {len(radius_outlier_indices)} more outliers)")

# ---------- APPLY DBSCAN ----------
print("Applying DBSCAN clustering...")
labels = np.array(pcd.cluster_dbscan(eps=eps, min_points=min_points, print_progress=True))
max_label = labels.max()
print(f"Initial clusters found: {max_label + 1}")

# ---------- COLLECT CLUSTERS ----------
clusters = []
for i in range(max_label + 1):
    indices = np.where(labels == i)[0]
    if len(indices) < min_cluster_size:
        continue
    cluster_points = np.asarray(pcd.points)[indices]
    clusters.append({
        "id": i,
        "indices": indices,
        "points": cluster_points,
        "centroid": np.mean(cluster_points, axis=0)
    })

print(f"Clusters after size filtering: {len(clusters)}")

# ---------- MERGE SPLIT CLUSTERS ----------
print("Merging vertically aligned clusters...")
merged_clusters = []
merged_ids = set()

def are_clusters_vertically_aligned(c1, c2):
    xy_dist = np.linalg.norm(c1["centroid"][:2] - c2["centroid"][:2])
    z_gap = abs(c1["centroid"][2] - c2["centroid"][2])
    return xy_dist < xy_thresh and z_gap < z_gap_thresh

for i, c1 in enumerate(clusters):
    if c1["id"] in merged_ids:
        continue
    merged_indices = list(c1["indices"])
    merged_cluster_ids = [c1["id"]]
    
    for j, c2 in enumerate(clusters):
        if i == j or c2["id"] in merged_ids:
            continue
        if are_clusters_vertically_aligned(c1, c2):
            merged_indices.extend(c2["indices"])
            merged_ids.add(c2["id"])
            merged_cluster_ids.append(c2["id"])
    
    cluster_points = np.asarray(pcd.points)[merged_indices]
    merged_clusters.append({
        "points": cluster_points,
        "original_ids": merged_cluster_ids,
        "point_count": len(cluster_points)
    })

# ---------- CALCULATE OBJECT PROPERTIES AND FILTER ----------
print("\n" + "="*60)
print(f"TOTAL OBJECTS IDENTIFIED: {len(merged_clusters)}")
print("="*60)

# Filter out unwanted objects
print(f"FILTERING OUT OBJECTS: {objects_to_remove}")
filtered_clusters = []
filtered_object_info = []

for i, cluster in enumerate(merged_clusters):
    original_object_num = i + 1
    if original_object_num not in objects_to_remove:
        filtered_clusters.append(cluster)
        
        points = cluster["points"]
        
        # Calculate bounding box dimensions
        min_coords = np.min(points, axis=0)
        max_coords = np.max(points, axis=0)
        dimensions = max_coords - min_coords
        
        # Calculate volume (approximate)
        volume = dimensions[0] * dimensions[1] * dimensions[2]
        
        # Calculate centroid
        centroid = np.mean(points, axis=0)
        
        obj_info = {
            "original_object_num": original_object_num,
            "filtered_object_num": len(filtered_clusters),
            "point_count": cluster["point_count"],
            "dimensions": dimensions,
            "volume": volume,
            "centroid": centroid,
            "min_coords": min_coords,
            "max_coords": max_coords
        }
        filtered_object_info.append(obj_info)

print(f"OBJECTS AFTER FILTERING: {len(filtered_clusters)}")
print("="*60)

# Print filtered object information
for obj in filtered_object_info:
    print(f"Object {obj['filtered_object_num']} (originally Object {obj['original_object_num']}):")
    print(f"  Points: {obj['point_count']}")
    print(f"  Dimensions (L×W×H): {obj['dimensions'][0]:.2f} × {obj['dimensions'][1]:.2f} × {obj['dimensions'][2]:.2f} mm")
    print(f"  Volume: {obj['volume']:.2f} mm³")
    print(f"  Centroid: ({obj['centroid'][0]:.2f}, {obj['centroid'][1]:.2f}, {obj['centroid'][2]:.2f})")
    print(f"  Bounding Box: Min({obj['min_coords'][0]:.2f}, {obj['min_coords'][1]:.2f}, {obj['min_coords'][2]:.2f}) to Max({obj['max_coords'][0]:.2f}, {obj['max_coords'][1]:.2f}, {obj['max_coords'][2]:.2f})")
    print("-" * 40)

def create_simple_label(object_num, position, size=8.0):
    """Create a simple but distinctive label for each object"""
    # Shared colors for object pairs
    label_colors = [
        [1, 0, 0],          # Red - Object 1 (shares with Object 3)
        [0, 0, 1],          # Blue - Object 2 (shares with Object 4)
        [1, 0, 0],          # Red - Object 3 (shares with Object 1)
        [0, 0, 1],          # Blue - Object 4 (shares with Object 2)
    ]
    
    # Use the appropriate color for this object number
    if object_num <= len(label_colors):
        label_color = label_colors[object_num - 1]
    else:
        # Fallback for more objects
        label_color = [0, 0, 0]  # Black
    
    # Create main label sphere
    label_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=size)
    label_sphere.translate(position)
    label_sphere.paint_uniform_color(label_color)
    
    return label_sphere

# ---------- DEFINE SIMPLE COLORS FOR REMAINING OBJECTS ----------
# Shared colors for object pairs
remaining_colors = [
    [1, 0, 0],          # Red - Object 1 (shares with Object 3)
    [0, 0, 1],          # Blue - Object 2 (shares with Object 4)
    [1, 0, 0],          # Red - Object 3 (shares with Object 1)
    [0, 0, 1],          # Blue - Object 4 (shares with Object 2)
]

remaining_color_names = ["Red", "Blue", "Red", "Blue"]

# ---------- INITIALIZE GEOMETRIES LIST ----------
geometries = []

# ---------- CREATE COMBINED OBJECTS AND BOUNDING BOXES ----------
print("\n" + "="*60)
print("CREATING COMBINED OBJECTS:")
print("="*60)

# Function to get object by filtered number
def get_object_by_number(obj_num):
    for i, obj in enumerate(filtered_object_info):
        if obj['filtered_object_num'] == obj_num:
            return obj, filtered_clusters[i]
    return None, None

combined_objects = []
combined_geometries = []

if len(filtered_object_info) >= 4:
    # Get objects and their clusters
    obj1_info, obj1_cluster = get_object_by_number(1)  # Red object
    obj2_info, obj2_cluster = get_object_by_number(2)  # Blue object
    obj3_info, obj3_cluster = get_object_by_number(3)  # Red object
    obj4_info, obj4_cluster = get_object_by_number(4)  # Blue object
    
    if all([obj1_info, obj2_info, obj3_info, obj4_info]):
        # Create Combined Object A: Objects 3 and 1 (Red objects)
        combined_points_A = np.vstack([obj3_cluster["points"], obj1_cluster["points"]])
        combined_pcd_A = o3d.geometry.PointCloud()
        combined_pcd_A.points = o3d.utility.Vector3dVector(combined_points_A)
        combined_pcd_A.paint_uniform_color([1, 0, 0])  # Red
        
        # Get bounding box for Combined Object A
        bbox_A = combined_pcd_A.get_axis_aligned_bounding_box()
        bbox_A.color = [0.8, 0, 0]  # Dark Red for bounding box
        min_coords_A = bbox_A.min_bound
        max_coords_A = bbox_A.max_bound
        dimensions_A = max_coords_A - min_coords_A
        volume_A = dimensions_A[0] * dimensions_A[1] * dimensions_A[2]
        centroid_A = (min_coords_A + max_coords_A) / 2
        
        # Create Combined Object B: Objects 4 and 2 (Blue objects)
        combined_points_B = np.vstack([obj4_cluster["points"], obj2_cluster["points"]])
        combined_pcd_B = o3d.geometry.PointCloud()
        combined_pcd_B.points = o3d.utility.Vector3dVector(combined_points_B)
        combined_pcd_B.paint_uniform_color([0, 0, 1])  # Blue
        
        # Get bounding box for Combined Object B
        bbox_B = combined_pcd_B.get_axis_aligned_bounding_box()
        bbox_B.color = [0, 0, 0.8]  # Dark Blue for bounding box
        min_coords_B = bbox_B.min_bound
        max_coords_B = bbox_B.max_bound
        dimensions_B = max_coords_B - min_coords_B
        volume_B = dimensions_B[0] * dimensions_B[1] * dimensions_B[2]
        centroid_B = (min_coords_B + max_coords_B) / 2
        
        # Store combined object information
        combined_objects = [
            {
                "name": "Combined Object A",
                "description": "Objects 3 & 1 (Red)",
                "original_objects": [obj3_info['original_object_num'], obj1_info['original_object_num']],
                "point_count": len(combined_points_A),
                "min_coords": min_coords_A,
                "max_coords": max_coords_A,
                "dimensions": dimensions_A,
                "volume": volume_A,
                "centroid": centroid_A,
                "color": "Red"
            },
            {
                "name": "Combined Object B", 
                "description": "Objects 4 & 2 (Blue)",
                "original_objects": [obj4_info['original_object_num'], obj2_info['original_object_num']],
                "point_count": len(combined_points_B),
                "min_coords": min_coords_B,
                "max_coords": max_coords_B,
                "dimensions": dimensions_B,
                "volume": volume_B,
                "centroid": centroid_B,
                "color": "Blue"
            }
        ]
        
        # Print detailed information about combined objects
        for i, obj in enumerate(combined_objects):
            print(f"{obj['name']} - {obj['description']}:")
            print(f"  Original Objects: {obj['original_objects']}")
            print(f"  Total Points: {obj['point_count']}")
            print(f"  Color: {obj['color']}")
            print(f"  Centroid: ({obj['centroid'][0]:.2f}, {obj['centroid'][1]:.2f}, {obj['centroid'][2]:.2f})")
            print(f"  Dimensions (L×W×H): {obj['dimensions'][0]:.2f} × {obj['dimensions'][1]:.2f} × {obj['dimensions'][2]:.2f} mm")
            print(f"  Volume: {obj['volume']:.2f} mm³")
            print(f"")
            print(f"  BOUNDING BOX COORDINATES:")
            print(f"    Min Corner: ({obj['min_coords'][0]:.2f}, {obj['min_coords'][1]:.2f}, {obj['min_coords'][2]:.2f})")
            print(f"    Max Corner: ({obj['max_coords'][0]:.2f}, {obj['max_coords'][1]:.2f}, {obj['max_coords'][2]:.2f})")
            print(f"")
            print(f"  BOUNDING BOX VERTICES (8 corners):")
            # Calculate all 8 vertices of the bounding box
            min_x, min_y, min_z = obj['min_coords']
            max_x, max_y, max_z = obj['max_coords']
            vertices = [
                (min_x, min_y, min_z),  # Bottom face
                (max_x, min_y, min_z),
                (max_x, max_y, min_z),
                (min_x, max_y, min_z),
                (min_x, min_y, max_z),  # Top face
                (max_x, min_y, max_z),
                (max_x, max_y, max_z),
                (min_x, max_y, max_z),
            ]
            for j, vertex in enumerate(vertices):
                print(f"    Vertex {j+1}: ({vertex[0]:.2f}, {vertex[1]:.2f}, {vertex[2]:.2f})")
            print("=" * 60)
        
        # Add geometries for visualization
        combined_geometries = [combined_pcd_A, bbox_A, combined_pcd_B, bbox_B]
        
        # Calculate height difference between combined objects
        height_diff_AB = centroid_B[2] - centroid_A[2]
        print(f"\nHEIGHT DIFFERENCE BETWEEN COMBINED OBJECTS:")
        print(f"Combined Object A (Red) height: {centroid_A[2]:.2f} mm")
        print(f"Combined Object B (Blue) height: {centroid_B[2]:.2f} mm")
        print(f"Height difference (B - A): {height_diff_AB:.2f} mm")
        if height_diff_AB > 0:
            print(f"→ Combined Object B (Blue) is {abs(height_diff_AB):.2f} mm HIGHER than Combined Object A (Red)")
        elif height_diff_AB < 0:
            print(f"→ Combined Object B (Blue) is {abs(height_diff_AB):.2f} mm LOWER than Combined Object A (Red)")
        else:
            print(f"→ Combined Objects A and B are at the SAME height")
        
    else:
        print("Error: Could not find all required objects for combining.")
        # Fallback: create individual colored objects
        for i, cluster in enumerate(filtered_clusters):
            if i < len(remaining_colors):
                cluster_pcd = o3d.geometry.PointCloud()
                cluster_pcd.points = o3d.utility.Vector3dVector(cluster["points"])
                cluster_pcd.paint_uniform_color(remaining_colors[i])
                combined_geometries.append(cluster_pcd)
else:
    print("Error: Not enough objects for combining.")
    # Fallback: create individual colored objects
    for i, cluster in enumerate(filtered_clusters):
        if i < len(remaining_colors):
            cluster_pcd = o3d.geometry.PointCloud()
            cluster_pcd.points = o3d.utility.Vector3dVector(cluster["points"])
            cluster_pcd.paint_uniform_color(remaining_colors[i])
            combined_geometries.append(cluster_pcd)

print("="*60)

# ---------- USE COMBINED GEOMETRIES FOR VISUALIZATION ----------
geometries = combined_geometries if combined_geometries else geometries

# ---------- CREATE SUMMARY TEXT ----------
print("\n" + "="*60)
print("SUMMARY STATISTICS (AFTER FILTERING):")
print("="*60)
total_points = sum([obj["point_count"] for obj in filtered_object_info])
avg_volume = np.mean([obj["volume"] for obj in filtered_object_info])
largest_obj = max(filtered_object_info, key=lambda x: x["volume"])
smallest_obj = min(filtered_object_info, key=lambda x: x["volume"])

print(f"Filtered Objects Displayed: {len(filtered_clusters)}")
print(f"Objects Removed: {len(objects_to_remove)}")
print(f"Total Points in Remaining Objects: {total_points}")
print(f"Average Object Volume: {avg_volume:.2f} mm³")
print(f"Largest Remaining Object: Object {largest_obj['filtered_object_num']} (Volume: {largest_obj['volume']:.2f} mm³)")
print(f"Smallest Remaining Object: Object {smallest_obj['filtered_object_num']} (Volume: {smallest_obj['volume']:.2f} mm³)")
print("="*60)

# ---------- CALCULATE HEIGHT DIFFERENCES ----------
print("\n" + "="*60)
print("HEIGHT DIFFERENCE ANALYSIS:")
print("="*60)

# Function to get object by filtered number
def get_object_by_number(obj_num):
    for obj in filtered_object_info:
        if obj['filtered_object_num'] == obj_num:
            return obj
    return None

# Calculate height differences between specified pairs
if len(filtered_object_info) >= 4:
    # Get objects
    object1 = get_object_by_number(1)  # Red object
    object2 = get_object_by_number(2)  # Blue object
    object3 = get_object_by_number(3)  # Red object
    object4 = get_object_by_number(4)  # Blue object
    
    if all([object1, object2, object3, object4]):
        # Height difference between Object 3 (Red) and Object 1 (Red)
        height_diff_3_1 = object3['centroid'][2] - object1['centroid'][2]
        
        # Height difference between Object 4 (Blue) and Object 2 (Blue)
        height_diff_4_2 = object4['centroid'][2] - object2['centroid'][2]
        
        print(f"Height Difference Analysis:")
        print(f"")
        print(f"Object 3 (Red, originally Object {object3['original_object_num']}) vs Object 1 (Red, originally Object {object1['original_object_num']}):")
        print(f"  Object 1 height (Z-centroid): {object1['centroid'][2]:.2f} mm")
        print(f"  Object 3 height (Z-centroid): {object3['centroid'][2]:.2f} mm")
        print(f"  Height difference (Object 3 - Object 1): {height_diff_3_1:.2f} mm")
        if height_diff_3_1 > 0:
            print(f"  → Object 3 (Red) is {abs(height_diff_3_1):.2f} mm HIGHER than Object 1 (Red)")
        elif height_diff_3_1 < 0:
            print(f"  → Object 3 (Red) is {abs(height_diff_3_1):.2f} mm LOWER than Object 1 (Red)")
        else:
            print(f"  → Object 3 (Red) and Object 1 (Red) are at the SAME height")
        
        print(f"")
        print(f"Object 4 (Blue, originally Object {object4['original_object_num']}) vs Object 2 (Blue, originally Object {object2['original_object_num']}):")
        print(f"  Object 2 height (Z-centroid): {object2['centroid'][2]:.2f} mm")
        print(f"  Object 4 height (Z-centroid): {object4['centroid'][2]:.2f} mm")
        print(f"  Height difference (Object 4 - Object 2): {height_diff_4_2:.2f} mm")
        if height_diff_4_2 > 0:
            print(f"  → Object 4 (Blue) is {abs(height_diff_4_2):.2f} mm HIGHER than Object 2 (Blue)")
        elif height_diff_4_2 < 0:
            print(f"  → Object 4 (Blue) is {abs(height_diff_4_2):.2f} mm LOWER than Object 2 (Blue)")
        else:
            print(f"  → Object 4 (Blue) and Object 2 (Blue) are at the SAME height")
        
        print(f"")
        print(f"ADDITIONAL HEIGHT COMPARISONS:")
        print(f"  Highest object: Object {max(filtered_object_info, key=lambda x: x['centroid'][2])['filtered_object_num']} at {max([obj['centroid'][2] for obj in filtered_object_info]):.2f} mm")
        print(f"  Lowest object: Object {min(filtered_object_info, key=lambda x: x['centroid'][2])['filtered_object_num']} at {min([obj['centroid'][2] for obj in filtered_object_info]):.2f} mm")
        print(f"  Total height range: {max([obj['centroid'][2] for obj in filtered_object_info]) - min([obj['centroid'][2] for obj in filtered_object_info]):.2f} mm")
        
    else:
        print("Error: Could not find all required objects for height comparison.")
else:
    print("Error: Not enough objects remaining for height comparison analysis.")

print("="*60)

# ---------- PRINT COLOR REFERENCE FOR REMAINING OBJECTS ----------
print("\n" + "="*60)
print("COLOR REFERENCE FOR REMAINING OBJECTS:")
print("="*60)
if len(filtered_object_info) >= 4:
    print(f"Object 1 (originally Object {filtered_object_info[0]['original_object_num']}): Red")
    print(f"Object 2 (originally Object {filtered_object_info[1]['original_object_num']}): Blue") 
    print(f"Object 3 (originally Object {filtered_object_info[2]['original_object_num']}): Red (same as Object 1)")
    print(f"Object 4 (originally Object {filtered_object_info[3]['original_object_num']}): Blue (same as Object 2)")
    print("")
    print("OBJECT PAIRS WITH SAME COLORS:")
    print("- Objects 1 & 3: Both RED")
    print("- Objects 2 & 4: Both BLUE")
else:
    for i, obj in enumerate(filtered_object_info):
        color_name = remaining_color_names[i] if i < len(remaining_color_names) else "Unknown"
        print(f"Object {obj['filtered_object_num']} (originally Object {obj['original_object_num']}): {color_name}")
print("="*60)

# ---------- VISUALIZE ----------
print("\nVisualizing objects...")
if len(combined_objects) == 2:
    print("VISUALIZATION:")
    print("- Combined Object A (Red): Objects 3 & 1 merged into one")
    print("- Combined Object B (Blue): Objects 4 & 2 merged into one") 
    print("- Dark Red bounding box around Combined Object A")
    print("- Dark Blue bounding box around Combined Object B")
    print("- All bounding box coordinates are printed above")
    print(f"- REMOVED OBJECTS: {objects_to_remove}")
    print("- Now showing 2 combined objects instead of 4 individual ones")
else:
    print("VISUALIZATION:")
    print("- Individual objects shown with assigned colors")
    print(f"- REMOVED OBJECTS: {objects_to_remove}")
    print(f"- Showing {len(filtered_clusters)} filtered objects")

# Create coordinate frame for reference
coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=50.0, origin=[0, 0, 0])
geometries.append(coord_frame)

# Determine window title based on visualization type
if len(combined_objects) == 2:
    window_title = f"Combined Objects - 2 Merged Objects from Original {len(filtered_clusters)} Objects"
else:
    window_title = f"Filtered Objects - {len(filtered_clusters)} Individual Objects"

o3d.visualization.draw_geometries(
    geometries,
    window_name=window_title,
    width=1200,
    height=800
)

# ---------- OPTIONAL: SAVE RESULTS ----------
save_results = input("\nDo you want to save the filtered segmentation results? (y/n): ").lower().strip()
if save_results == 'y':
    # Save individual filtered clusters
    for i in range(len(filtered_clusters)):
        cluster = filtered_clusters[i]
        obj_info = filtered_object_info[i]
        cluster_pcd = o3d.geometry.PointCloud()
        cluster_pcd.points = o3d.utility.Vector3dVector(cluster["points"])
        if i < len(remaining_colors):
            cluster_pcd.paint_uniform_color(remaining_colors[i])
        
        color_name = remaining_color_names[i] if i < len(remaining_color_names) else "unknown"
        output_path = f"filtered_object_{obj_info['filtered_object_num']}_{color_name.lower()}_cluster.pcd"
        o3d.io.write_point_cloud(output_path, cluster_pcd)
        print(f"Saved Filtered Object {obj_info['filtered_object_num']} ({color_name}) to {output_path}")
    
    # Save summary to text file
    with open("filtered_segmentation_summary.txt", "w") as f:
        f.write(f"Filtered Point Cloud Segmentation Results\n")
        f.write(f"==========================================\n\n")
        f.write(f"Objects Removed: {objects_to_remove}\n")
        f.write(f"Remaining Objects: {len(filtered_clusters)}\n\n")
        f.write("Color Reference for Remaining Objects:\n")
        for i in range(len(filtered_clusters)):
            if i < len(remaining_color_names):
                f.write(f"Object {i+1} (originally Object {filtered_object_info[i]['original_object_num']}): {remaining_color_names[i]}\n")
        f.write("\nDetailed Information:\n")
        f.write("-" * 40 + "\n")
        
        for obj in filtered_object_info:
            color_name = remaining_color_names[obj['filtered_object_num']-1] if obj['filtered_object_num']-1 < len(remaining_color_names) else "unknown"
            f.write(f"Object {obj['filtered_object_num']} ({color_name}) - originally Object {obj['original_object_num']}:\n")
            f.write(f"  Points: {obj['point_count']}\n")
            f.write(f"  Dimensions (L×W×H): {obj['dimensions'][0]:.2f} × {obj['dimensions'][1]:.2f} × {obj['dimensions'][2]:.2f} mm\n")
            f.write(f"  Volume: {obj['volume']:.2f} mm³\n")
            f.write(f"  Centroid: ({obj['centroid'][0]:.2f}, {obj['centroid'][1]:.2f}, {obj['centroid'][2]:.2f})\n")
            f.write("-" * 40 + "\n")
    
    print("Filtered summary saved to filtered_segmentation_summary.txt")

print("\nFiltered segmentation complete with simple colors!")

# ---------- FUNCTION FOR RABBITMQ INTEGRATION ----------
def process_inductionpad_boundingbox(file_path):
    """Process the PCD file and return bounding box coordinates for inductionpad."""
    try:
        # ---------- CONFIGURE PARAMETERS ----------
        eps = 15                     # DBSCAN distance threshold in mm
        min_points = 20               # Minimum points per cluster
        xy_thresh = 50                # XY distance for vertical merge (mm)
        z_gap_thresh = 100            # Max vertical gap for merging (mm)
        min_cluster_size = 500        # Ignore clusters smaller than this

        # Additional noise reduction parameters
        outlier_nb_neighbors = 30     # Increased for better noise removal
        outlier_std_ratio = 1.5       # Increased for stricter noise removal

        # OBJECT FILTERING - Specify which objects to REMOVE/FILTER OUT
        objects_to_remove = [1, 2, 4, 5, 6, 7, 9, 10, 11, 14]  # List of object numbers to exclude

        # ---------- LOAD AND CLEAN POINT CLOUD ----------
        pcd = o3d.io.read_point_cloud(file_path)
        
        # Remove statistical outliers
        pcd, outlier_indices = pcd.remove_statistical_outlier(
            nb_neighbors=outlier_nb_neighbors, 
            std_ratio=outlier_std_ratio
        )

        # Additional radius outlier removal for better noise reduction
        pcd, radius_outlier_indices = pcd.remove_radius_outlier(nb_points=10, radius=20.0)

        # ---------- APPLY DBSCAN ----------
        labels = np.array(pcd.cluster_dbscan(eps=eps, min_points=min_points, print_progress=False))
        max_label = labels.max()

        # ---------- COLLECT CLUSTERS ----------
        clusters = []
        for i in range(max_label + 1):
            indices = np.where(labels == i)[0]
            if len(indices) < min_cluster_size:
                continue
            cluster_points = np.asarray(pcd.points)[indices]
            clusters.append({
                "id": i,
                "indices": indices,
                "points": cluster_points,
                "centroid": np.mean(cluster_points, axis=0)
            })

        # ---------- MERGE SPLIT CLUSTERS ----------
        merged_clusters = []
        merged_ids = set()

        def are_clusters_vertically_aligned(c1, c2):
            xy_dist = np.linalg.norm(c1["centroid"][:2] - c2["centroid"][:2])
            z_gap = abs(c1["centroid"][2] - c2["centroid"][2])
            return xy_dist < xy_thresh and z_gap < z_gap_thresh

        for i, c1 in enumerate(clusters):
            if c1["id"] in merged_ids:
                continue
            merged_indices = list(c1["indices"])
            merged_cluster_ids = [c1["id"]]
            
            for j, c2 in enumerate(clusters):
                if i == j or c2["id"] in merged_ids:
                    continue
                if are_clusters_vertically_aligned(c1, c2):
                    merged_indices.extend(c2["indices"])
                    merged_ids.add(c2["id"])
                    merged_cluster_ids.append(c2["id"])
            
            cluster_points = np.asarray(pcd.points)[merged_indices]
            merged_clusters.append({
                "points": cluster_points,
                "original_ids": merged_cluster_ids,
                "point_count": len(cluster_points)
            })

        # ---------- CALCULATE OBJECT PROPERTIES AND FILTER ----------
        # Filter out unwanted objects
        filtered_clusters = []
        filtered_object_info = []

        for i, cluster in enumerate(merged_clusters):
            original_object_num = i + 1
            if original_object_num not in objects_to_remove:
                filtered_clusters.append(cluster)
                
                points = cluster["points"]
                
                # Calculate bounding box dimensions
                min_coords = np.min(points, axis=0)
                max_coords = np.max(points, axis=0)
                dimensions = max_coords - min_coords
                
                # Calculate volume (approximate)
                volume = dimensions[0] * dimensions[1] * dimensions[2]
                
                # Calculate centroid
                centroid = np.mean(points, axis=0)
                
                obj_info = {
                    "original_object_num": original_object_num,
                    "filtered_object_num": len(filtered_clusters),
                    "point_count": cluster["point_count"],
                    "dimensions": dimensions,
                    "volume": volume,
                    "centroid": centroid,
                    "min_coords": min_coords,
                    "max_coords": max_coords
                }
                filtered_object_info.append(obj_info)

        # ---------- CREATE COMBINED OBJECTS AND BOUNDING BOXES ----------
        # Function to get object by filtered number
        def get_object_by_number(obj_num):
            for i, obj in enumerate(filtered_object_info):
                if obj['filtered_object_num'] == obj_num:
                    return obj, filtered_clusters[i]
            return None, None

        combined_objects = []

        if len(filtered_object_info) >= 4:
            # Get objects and their clusters
            obj1_info, obj1_cluster = get_object_by_number(1)  # Red object
            obj2_info, obj2_cluster = get_object_by_number(2)  # Blue object
            obj3_info, obj3_cluster = get_object_by_number(3)  # Red object
            obj4_info, obj4_cluster = get_object_by_number(4)  # Blue object
            
            if all([obj1_info, obj2_info, obj3_info, obj4_info]):
                # Create Combined Object A: Objects 3 and 1 (Red objects)
                combined_points_A = np.vstack([obj3_cluster["points"], obj1_cluster["points"]])
                combined_pcd_A = o3d.geometry.PointCloud()
                combined_pcd_A.points = o3d.utility.Vector3dVector(combined_points_A)
                
                # Get bounding box for Combined Object A
                bbox_A = combined_pcd_A.get_axis_aligned_bounding_box()
                min_coords_A = bbox_A.min_bound
                max_coords_A = bbox_A.max_bound
                dimensions_A = max_coords_A - min_coords_A
                centroid_A = (min_coords_A + max_coords_A) / 2
                
                # Create Combined Object B: Objects 4 and 2 (Blue objects)
                combined_points_B = np.vstack([obj4_cluster["points"], obj2_cluster["points"]])
                combined_pcd_B = o3d.geometry.PointCloud()
                combined_pcd_B.points = o3d.utility.Vector3dVector(combined_points_B)
                
                # Get bounding box for Combined Object B
                bbox_B = combined_pcd_B.get_axis_aligned_bounding_box()
                min_coords_B = bbox_B.min_bound
                max_coords_B = bbox_B.max_bound
                dimensions_B = max_coords_B - min_coords_B
                centroid_B = (min_coords_B + max_coords_B) / 2
                
                # Return bounding box coordinates
                return {
                    "success": True,
                    "combined_object_A": {
                        "x1": float(min_coords_A[0]),
                        "y1": float(min_coords_A[1]),
                        "z1": float(min_coords_A[2]),
                        "dx1": float(dimensions_A[0]),
                        "dy1": float(dimensions_A[1]),
                        "dz1": float(dimensions_A[2])
                    },
                    "combined_object_B": {
                        "x2": float(min_coords_B[0]),
                        "y2": float(min_coords_B[1]),
                        "z2": float(min_coords_B[2]),
                        "dx2": float(dimensions_B[0]),
                        "dy2": float(dimensions_B[1]),
                        "dz2": float(dimensions_B[2])
                    }
                }
            else:
                return {"error": "Could not find all required objects for combining"}
        else:
            return {"error": "Not enough objects for combining"}
            
    except Exception as e:
        return {"error": f"Error processing inductionpad bounding box: {str(e)}"}
