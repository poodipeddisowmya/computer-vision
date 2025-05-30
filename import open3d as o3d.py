import open3d as o3d
import numpy as np
from scipy.spatial.distance import pdist

def load_pcd(file_path):
    """Load a PCD file using Open3D."""
    return o3d.io.read_point_cloud(file_path)

def pick_points(pcd):
    """Allow the user to pick points from the visualized point cloud."""
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window()
    vis.add_geometry(pcd)
    vis.run()
    vis.destroy_window()
    return vis.get_picked_points()

def compute_diameter(pcd, selected_indices):
    """Compute the diameter based on selected points."""
    points = np.asarray(pcd.points)
    selected_points = points[selected_indices]
    if len(selected_points) < 2:
        return None, None
    diameter = np.max(pdist(selected_points))
    center = np.mean(selected_points, axis=0)
    return diameter, center

def detect_green_region(pcd):
    """Detect green-colored region (handle) based on color thresholding and compute its direction."""
    colors = np.asarray(pcd.colors)
    green_mask = (colors[:, 1] > colors[:, 0]) & (colors[:, 1] > colors[:, 2])
    indices = np.where(green_mask)[0]
    green_pcd = pcd.select_by_index(indices)
    
    if len(indices) == 0:
        return None, None, None
    
    points = np.asarray(green_pcd.points)
    center_handle = np.mean(points, axis=0)
    
    # Compute direction using PCA
    if len(points) < 3:
        return green_pcd, center_handle, None
    cov_matrix = np.cov(points.T)
    eigenvalues, eigenvectors = np.linalg.eig(cov_matrix)
    handle_direction = eigenvectors[:, np.argmax(eigenvalues)]
    
    return green_pcd, center_handle, handle_direction

def compute_orientation_vector(pcd):
    """Compute the orientation vector using PCA."""
    points = np.asarray(pcd.points)
    if len(points) < 3:
        return None, None
    mean = np.mean(points, axis=0)
    cov_matrix = np.cov(points.T)
    eigenvalues, eigenvectors = np.linalg.eig(cov_matrix)
    principal_vector = eigenvectors[:, np.argmax(eigenvalues)]
    return mean, principal_vector

def visualize_results(pcd, center_utensil, center_handle, orientation, handle_direction):
    """Visualize the utensil, handle, handle direction, and handle orientation vector."""
    utensil_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=5)
    utensil_sphere.paint_uniform_color([1, 0, 0])
    utensil_sphere.translate(center_utensil)
    
    handle_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=5)
    handle_sphere.paint_uniform_color([0, 1, 0])
    handle_sphere.translate(center_handle)
    
    arrow = o3d.geometry.TriangleMesh.create_arrow(
        cylinder_radius=2, cone_radius=5, cylinder_height=50, cone_height=10)
    arrow.translate(center_handle)
    
    z_axis = np.array([0, 0, 1])
    rotation_axis = np.cross(z_axis, orientation)
    rotation_angle = np.arccos(np.dot(z_axis, orientation))
    if np.linalg.norm(rotation_axis) > 1e-6:
        rotation_axis /= np.linalg.norm(rotation_axis)
        R = o3d.geometry.get_rotation_matrix_from_axis_angle(rotation_axis * rotation_angle)
        arrow.rotate(R, center_handle)
    
    # Visualizing handle direction
    handle_arrow = o3d.geometry.TriangleMesh.create_arrow(
        cylinder_radius=2, cone_radius=5, cylinder_height=50, cone_height=10)
    handle_arrow.paint_uniform_color([0, 0, 1])
    handle_arrow.translate(center_handle)
    
    if handle_direction is not None:
        rotation_axis_handle = np.cross(z_axis, handle_direction)
        rotation_angle_handle = np.arccos(np.dot(z_axis, handle_direction))
        if np.linalg.norm(rotation_axis_handle) > 1e-6:
            rotation_axis_handle /= np.linalg.norm(rotation_axis_handle)
            R_handle = o3d.geometry.get_rotation_matrix_from_axis_angle(rotation_axis_handle * rotation_angle_handle)
            handle_arrow.rotate(R_handle, center_handle)
    
    o3d.visualization.draw_geometries([pcd, utensil_sphere, handle_sphere, arrow, handle_arrow])

def main():
    pcd_path = input("Enter PCD file path: ")
    pcd = load_pcd(pcd_path)
    
    selected_indices = pick_points(pcd)
    
    if selected_indices:
        diameter, center_utensil = compute_diameter(pcd, selected_indices)
        print(f"Computed Diameter: {diameter}")
        print(f"Center of Utensil: {center_utensil}")
        
        green_pcd, center_handle, handle_direction = detect_green_region(pcd)
        if center_handle is not None:
            print(f"Center of Handle: {center_handle}")
            print(f"Handle Direction: {handle_direction}")
            _, orientation = compute_orientation_vector(green_pcd)
            visualize_results(pcd, center_utensil, center_handle, orientation, handle_direction)
        else:
            print("No green region detected.")
    else:
        print("No points selected.")

if __name__ == "__main__":
    main()




