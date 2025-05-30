import open3d as o3d
import numpy as np

def load_pcd(file_path):
    """Load a PCD file using Open3D."""
    pcd = o3d.io.read_point_cloud(file_path)
    return pcd

def pick_points(pcd):
    """Visualize the point cloud and allow point selection."""
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window()
    vis.add_geometry(pcd)
    vis.run()
    vis.destroy_window()
    
    picked_points = vis.get_picked_points()
    picked_coords = np.asarray(pcd.points)[picked_points]
    
    print("Selected Points' Coordinates:")
    for i, coord in enumerate(picked_coords):
        print(f"Point {i + 1}: {coord}")
    
    return picked_coords

# Define file path
pcd_path = r"C:\Users\Sowmya\OneDrive\Desktop\SHARMA\M3 UTENSIL.pcd"

# Load the point cloud
pcd = load_pcd(pcd_path)

# Visualize and pick points
picked_coords = pick_points(pcd)
