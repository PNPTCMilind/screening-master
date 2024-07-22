import numpy as np
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import precision_score, recall_score
import pickle
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

def train_model(data):
    # Encode categorical variables
    categorical_columns = [
        'country_code', 'region', 'city', 
        'category_list', 'category_groups_list', 'last_round_investment_type'
    ]

    encoders = {}
    for col in categorical_columns:
        le = LabelEncoder()
        data[col] = le.fit_transform(data[col].astype(str))
        encoders[col] = le

    # Encode target variable
    target_encoder = LabelEncoder()
    data['outcome'] = target_encoder.fit_transform(data['outcome'].astype(str))

    # Define features and print included and excluded features
    excluded_features = [
        'uuid_org', 'name_org', 'permalink_org', 'domain', 'homepage_url', 
        'address', 'postal_code', 'short_description', 'facebook_url', 
        'linkedin_url', 'twitter_url', 'founded_on', 'last_funding_on', 
        'closed_on', 'total_funding_currency_code', 'outcome', 'state_code', 
        'status', 'total_funding', 'category_groups_list'
    ]
    X = data.drop(columns=excluded_features)

    # Save the column names
    column_names = X.columns.tolist()

    # Binary targets for specified classifications
    data['IPO_vs_Other'] = (data['outcome'] == target_encoder.transform(['IP'])[0]).astype(int)
    data['FR_vs_Other'] = (data['outcome'] == target_encoder.transform(['FR'])[0]).astype(int)
    data['NE_vs_Other'] = (data['outcome'] == target_encoder.transform(['NE'])[0]).astype(int)
    data['AC_vs_Other'] = (data['outcome'] == target_encoder.transform(['AC'])[0]).astype(int)
    data['CL_vs_Other'] = (data['outcome'] == target_encoder.transform(['CL'])[0]).astype(int)

    # Define classifiers
    classifiers = {
        'IPO_vs_Other_RF': RandomForestClassifier(),
        'FR_vs_Other_RF': RandomForestClassifier(),
        'NE_vs_Other_RF': RandomForestClassifier(),
        'CL_vs_Other_RF': RandomForestClassifier(),
        'AC_vs_Other_GB': GradientBoostingClassifier()
    }

    # Train and evaluate classifiers
    results = {}
    positive_predictions = {
        'IPO_vs_Other_RF': {}, 'FR_vs_Other_RF': {}, 'NE_vs_Other_RF': {}, 'CL_vs_Other_RF': {}, 'AC_vs_Other_GB': {}
    }

    for target, clf in classifiers.items():
        outcome, model_type = target.rsplit('_', 1)
        y = data[outcome]
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        precision_scores = []
        recall_scores = []
        
        for train_index, test_index in skf.split(X, y):
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
            
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)
            y_proba = clf.predict_proba(X_test)[:, 1]  # Probability of the positive class
            
            precision_scores.append(precision_score(y_test, y_pred, zero_division=0))
            recall_scores.append(recall_score(y_test, y_pred, zero_division=0))
            
            # Identify true positive predictions with their probabilities
            for i in range(len(y_test)):
                if y_pred[i] == 1 and y_test.iloc[i] == y_pred[i]:
                    index = X_test.index[i]
                    if index not in positive_predictions[target]:
                        positive_predictions[target][index] = {}
                    positive_predictions[target][index][outcome] = y_proba[i]
        
        results[target] = {
            'mean_precision': np.mean(precision_scores),
            'std_precision': np.std(precision_scores),
            'mean_recall': np.mean(recall_scores),
            'std_recall': np.std(recall_scores)
        }
        
        # Train on the full dataset for predictions
        clf.fit(X, y)
        data[f'{outcome}_{model_type}_Prediction'] = clf.predict(X)
        data[f'{outcome}_{model_type}_Probability'] = clf.predict_proba(X)[:, 1]

        print(f"{target}: Mean precision = {np.mean(precision_scores):.4f}, Std = {np.std(precision_scores):.4f}")
        print(f"{target}: Mean recall = {np.mean(recall_scores):.4f}, Std = {np.std(recall_scores):.4f}")

    # Save training and evaluation results to a file
    with open('model_results.pkl', 'wb') as file:
        pickle.dump({
            'results': results,
            'positive_predictions': positive_predictions
        }, file)

    # Save the trained classifiers
    with open('final_models.pkl', 'wb') as file:
        pickle.dump(classifiers, file)

    # Save the label encoders
    with open('label_encoders.pkl', 'wb') as file:
        pickle.dump(encoders, file)

    # Save the column names
    with open('column_names.pkl', 'wb') as file:
        pickle.dump(column_names, file)

    # Save the target encoder
    with open('target_encoder.pkl', 'wb') as file:
        pickle.dump(target_encoder, file)

@app.route("/", methods=["GET", "POST"])
def test_novel_datapoint():
    print("Index route accessed")
    if request.method == "POST":
        try:
            new_company_info = {
                'country_code': request.form['country_code'],
                'region': request.form['region'],
                'city': request.form['city'],
                'category_list': request.form['category_list'],
                'category_groups_list': request.form['category_groups_list'],
                'last_round_investment_type': request.form['last_round_investment_type'],
                'num_funding_rounds': int(request.form['num_funding_rounds']),
                'total_funding_usd': float(request.form['total_funding_usd']),
                'age_months': int(request.form['age_months']),
                'has_facebook_url': int(request.form.get('has_facebook_url', 0)),
                'has_twitter_url': int(request.form.get('has_twitter_url', 0)),
                'has_linkedin_url': int(request.form.get('has_linkedin_url', 0)),
                'round_count': int(request.form['round_count']),
                'raised_amount_usd': float(request.form['raised_amount_usd']),
                'last_round_raised_amount_usd': float(request.form['last_round_raised_amount_usd']),
                'last_round_post_money_valuation': float(request.form['last_round_post_money_valuation']),
                'last_round_timelapse_months': int(request.form['last_round_timelapse_months']),
                'investor_countup': int(request.form['investor_countup']),
                'last_round_investor_count': int(request.form['last_round_investor_count']),
                'founders_dif_country_count': int(request.form['founders_dif_country_count']),
                'founders_male_count': int(request.form['founders_male_count']),
                'founders_female_count': int(request.form['founders_female_count']),
                'founders_degree_count_total': int(request.form['founders_degree_count_total']),
                'founders_degree_count_max': int(request.form['founders_degree_count_max']),
                'founders_degree_count_mean': float(request.form['founders_degree_count_mean'])
            }

            print("New company info collected:")
            print(new_company_info)

            with open('./final_models.pkl', 'rb') as file:
                classifiers = pickle.load(file)
                print("Classifiers loaded")
            
            with open('./label_encoders.pkl', 'rb') as file:
                encoders = pickle.load(file)
                print("Encoders loaded")
            
            with open('./column_names.pkl', 'rb') as file:
                column_names = pickle.load(file)
                print("Column names loaded")

            def encode_and_handle_unseen(column, value):
                encoder = encoders[column]
                if value not in encoder.classes_:
                    encoder.classes_ = np.append(encoder.classes_, value)
                return encoder.transform([value])[0]

            new_company_df = pd.DataFrame([new_company_info])
            print("New company DataFrame created:")
            print(new_company_df)

            categorical_columns = [
                'country_code', 'region', 'city', 'category_list',
                'category_groups_list', 'last_round_investment_type'
            ]
            for col in categorical_columns:
                new_company_df[col] = new_company_df[col].apply(lambda x: encode_and_handle_unseen(col, x))
                print(f"Encoded {col}:")
                print(new_company_df[col])

            new_company_df = new_company_df.reindex(columns=column_names, fill_value=0)
            print("Reindexed DataFrame:")
            print(new_company_df)

            predictions = {}
            probabilities = {}

            for target, clf in classifiers.items():
                predictions[target] = int(clf.predict(new_company_df)[0])
                probabilities[target] = float(clf.predict_proba(new_company_df)[:, 1][0])
                print(f"Predictions for {target}: {predictions[target]}")
                print(f"Probabilities for {target}: {probabilities[target]}")

            results = {
                "IPO Prediction": (predictions['IPO_vs_Other_RF'], probabilities['IPO_vs_Other_RF']),
                "FR Prediction": (predictions['FR_vs_Other_RF'], probabilities['FR_vs_Other_RF']),
                "NE Prediction": (predictions['NE_vs_Other_RF'], probabilities['NE_vs_Other_RF']),
                "CL Prediction": (predictions['CL_vs_Other_RF'], probabilities['CL_vs_Other_RF']),
                "AC Prediction": (predictions['AC_vs_Other_GB'], probabilities['AC_vs_Other_GB'])
            }

            print("Results calculated")
            return jsonify(results=results)

        except Exception as e:
            print(f"An error occurred: {e}")
            return jsonify(error=str(e))

    return render_template("index.html")
    

def main():
    print("Main function")
    # data = pd.read_csv('unique_filtered_final_with_target_variable.csv')
    # data_column_names = data.columns
    # print("Data loaded")    
    # train_model(data)


if __name__ == "__main__":
    main()
    print("Starting Flask app")
    app.run(debug=True, host='0.0.0.0', port=8080)
