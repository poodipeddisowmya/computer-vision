import open3d as o3d
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial.distance import pdist

def load_pcd(file_path):
    return o3d.io.read_point_cloud(file_path)

def pick_points(pcd):
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window()
    vis.add_geometry(pcd)
    vis.run()
    vis.destroy_window()
    return vis.get_picked_points()

def compute_diameter(pcd, selected_indices):
    points = np.asarray(pcd.points)
    selected_points = points[selected_indices]
    if len(selected_points) < 2:
        return None, None
    diameter = np.max(pdist(selected_points))
    center = np.mean(selected_points, axis=0)
    return diameter, center

def compute_orientation_vector(points):
    if len(points) < 3:
        return None
    mean = np.mean(points, axis=0)
    centered = points - mean
    cov_matrix = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov_matrix)
    principal_axis = eigvecs[:, np.argmax(eigvals)]
    return mean, principal_axis

def detect_green_region(pcd, min_expected_x=180, max_expected_x=300):
    colors = np.asarray(pcd.colors)
    points = np.asarray(pcd.points)

    green_mask = (colors[:, 1] > 1.1 * colors[:, 0]) & (colors[:, 1] > 1.1 * colors[:, 2])
    valid_x_range = (points[:, 0] > min_expected_x) & (points[:, 0] < max_expected_x)
    indices = np.where(green_mask & valid_x_range)[0]

    green_pcd = pcd.select_by_index(indices)
    print(f"Number of detected green points: {len(indices)}")

    if len(indices) == 0:
        return None, None, None

    green_points = np.asarray(green_pcd.points)
    center_handle = np.mean(green_points, axis=0)
    mean, orientation_vector = compute_orientation_vector(green_points)

    # Debug: 3D scatter and histogram
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(green_points[:, 0], green_points[:, 1], green_points[:, 2], c='g')
    ax.set_xlabel('X Coordinate')
    ax.set_ylabel('Y Coordinate')
    ax.set_zlabel('Z Coordinate')
    ax.set_title('Scatter Plot of Detected Green Region')
    plt.show()

    plt.hist(green_points[:, 0], bins=20, color='green')
    plt.xlabel("X Coordinate")
    plt.ylabel("Frequency")
    plt.title("Distribution of X Coordinates in Green Region")
    plt.show()

    return green_pcd, center_handle, orientation_vector

def visualize_orientation(pcd, green_pcd, center_handle, orientation_vector):
    # Normalize orientation vector
    orientation_vector = orientation_vector / np.linalg.norm(orientation_vector)

    # Sphere at handle center
    handle_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=5)
    handle_sphere.paint_uniform_color([0, 0, 1])
    handle_sphere.translate(center_handle)

    # Arrow for orientation vector
    arrow = o3d.geometry.TriangleMesh.create_arrow(
        cylinder_radius=1, cone_radius=2, cylinder_height=50, cone_height=10
    )
    arrow.paint_uniform_color([1, 0, 0])  # Red arrow

    z_axis = np.array([0, 0, 1])  # Reference axis
    rotation_axis = np.cross(z_axis, orientation_vector)
    cos_angle = np.clip(np.dot(z_axis, orientation_vector) / (
        np.linalg.norm(z_axis) * np.linalg.norm(orientation_vector)), -1.0, 1.0)
    rotation_angle = np.arccos(cos_angle)

    if np.linalg.norm(rotation_axis) > 1e-6:
        rotation_axis /= np.linalg.norm(rotation_axis)
        R = o3d.geometry.get_rotation_matrix_from_axis_angle(rotation_axis * rotation_angle)
        arrow.rotate(R, center=(0, 0, 0))

    arrow.translate(center_handle)

    # Visualize everything
    o3d.visualization.draw_geometries([pcd, green_pcd, handle_sphere, arrow])

def main():
    # Fixed PCD path
    pcd_path = r"C:\Users\Sowmya\OneDrive\Desktop\SHARMA\M3 UTENSIL.pcd"
    pcd = load_pcd(pcd_path)

    selected_indices = pick_points(pcd)

    if selected_indices:
        diameter, center_utensil = compute_diameter(pcd, selected_indices)
        print(f"Computed Diameter: {diameter}")
        print(f"Center of Utensil: {center_utensil}")

        green_pcd, center_handle, orientation_vector = detect_green_region(pcd)
        if center_handle is not None and orientation_vector is not None:
            print(f"Handle Center: {center_handle}")
            print(f"Orientation Vector: {orientation_vector}")
            visualize_orientation(pcd, green_pcd, center_handle, orientation_vector)
        else:
            print("Green region or orientation could not be determined.")
    else:
        print("No points selected.")

if __name__ == "__main__":
    main()




