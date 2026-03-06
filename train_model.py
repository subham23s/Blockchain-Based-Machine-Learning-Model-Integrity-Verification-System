from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
import joblib

# 1️⃣ Load Iris dataset
iris = load_iris()
X = iris.data
y = iris.target

# 2️⃣ Split dataset into training and testing
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 3️⃣ Train Logistic Regression model
model = LogisticRegression(max_iter=200)
model.fit(X_train, y_train)

# 4️⃣ Evaluate model
y_pred = model.predict(X_test)

print("Accuracy:", accuracy_score(y_test, y_pred))
print("Confusion Matrix:\n", confusion_matrix(y_test, y_pred))

# 5️⃣ Save trained model to file
joblib.dump(model, "iris_model.joblib")

print("Model saved as iris_model.joblib")