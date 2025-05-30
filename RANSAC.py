import open3d as o3d
import numpy as np

def manual_point_selection(pcd):
    print("\nSelect handle points manually. Use: \n")
    print("  - Left-click to select points\n  - Press 'Q' to confirm selection\n")
    
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window()
    vis.add_geometry(pcd)
    vis.run()
    vis.destroy_window()
    
    selected_indices = vis.get_picked_points()
    selected_points = np.asarray(pcd.points)[selected_indices]
    
    return selected_points

# Example Usage
if __name__ == "__main__":
    file_path = input("Enter PCD file path: ")
    pcd = o3d.io.read_point_cloud(file_path)
    
    selected_points = manual_point_selection(pcd)
    if len(selected_points) > 0:
        center_of_handle = np.mean(selected_points, axis=0)
        print("\nManual Handle Center:", center_of_handle)
    else:
        print("No points selected!")























