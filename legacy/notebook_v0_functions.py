import json
import pandas as pd
from glob import glob
import zipfile
import os
import requests, zipfile, io, os


def load_and_extract_match_data(data_folder = "wpl_data"):

  all_files = glob(os.path.join("wpl_data", "*.json")) # Assuming JSON files are directly in the extracted directory
  matches_list = [] # Initialized matches_list
  errors = [] # Corrected typo and initialized errors

  for file in all_files:
      try: # Added try block
          with open(file, 'r', encoding='utf-8') as f:
              data  = json.load(f)
              if 'info' in data and 'innings' in data:
                matches_list.append(data)
              else:
                errors.append(f"Error: Missing 'info' or 'innings' in file {file}") # More descriptive error message
      except Exception as e:
          print(f"Error loading file {file}: {e}")

  extracted_data = [] # Renamed to avoid conflict with 'data' inside loop
  for match_info in matches_list:
    info = match_info['info']

    # Use .get() for safe access to outcome and winner
    outcome = info.get('outcome')
    if 'outcome' not in info or 'winner' not in info['outcome']:
                continue

    winner = outcome['winner'] # Now this should be safe
    teams = info['teams']
    # Get team names first, then use them to get player lists
    team_a_name = match_info['info']['teams'][0]
    team_b_name = match_info['info']['teams'][1]

    extracted_data.append({
        'teamAplayers': info['players'][team_a_name],
        'teamBplayers': info['players'][team_b_name],
        'teamA': team_a_name,
        'teamB': team_b_name,
        'venue': info['venue'],
        'date': match_info['meta']['created'],
        'toss_winner': info['toss']['winner'],
        'toss_decision': info['toss']['decision'],
        'winner': 1 if winner == team_a_name else 0
    })


  if not extracted_data:
      print("Warning: No match data extracted. Returning empty DataFrame with expected columns.")
      # Return an empty DataFrame with the expected columns to prevent KeyError in build_match_features
      return pd.DataFrame(columns=[
          'teamAplayers', 'teamBplayers', 'teamA', 'teamB', 'venue', 'date',
          'toss_winner', 'toss_decision', 'winner'
      ])

  df = pd.DataFrame(extracted_data).sort_values(['date']).reset_index(drop=True)



  return df

##ball by ball data

def load_ball_by_ball_data(data_folder ='wpl_data'): # Changed default data_folder
  files = glob(os.path.join(data_folder, "*.json"))
  all_balls_records = [] # Initialized to accumulate all ball records

  for file in files:
      try:
          with open(file, 'r', encoding='utf-8') as f:
              match = json.load(f)

          info = match['info']
          if 'outcome' not in info or 'winner' not in info['outcome']:
              continue

          teams = info['teams']
          winner = info['outcome']['winner']
          team_a_name = info['teams'][0] # Define team names from current match info
          team_b_name = info['teams'][1]

          for innings_idx, innings_dict in enumerate(match.get('innings', [])): # Use .get() for safety and correctly unpack
            batting_team = innings_dict['team']
            innings_num = innings_idx + 1 # 1-based indexing for innings
            bowling_team = team_a_name if batting_team == team_b_name else team_b_name

            batting_team_won = 1 if batting_team == winner else 0

            # Initialize cumulative counters
            cumulative_runs = 0
            cumulative_wickets = 0
            balls_faced = 0
            runs_history = []

            for over_num,over_dict in enumerate(innings_dict.get('overs', [])): # Use .get() for safety
              for ball_num,delivery in enumerate(over_dict['deliveries']):
                balls_faced += 1
                cumulative_runs += delivery['runs']['total']
                runs_history.append(delivery['runs']['total'])
                runs_last_6_overs = sum(runs_history[-36:]) if len(runs_history) >= 36 else sum(runs_history)

                if delivery.get('wickets'): # Safely check if 'wickets' key exists and has a value
                  cumulative_wickets += 1
                ball_record = {
                    'runs_last_6_overs':runs_last_6_overs,
                    'batting_team':batting_team,
                    'innings': innings_num,
                    'bowling_team':bowling_team,
                    'cum_runs':cumulative_runs,
                    'balls_faced':balls_faced,
                    'cum_wickets':cumulative_wickets,
                    'over_num':over_num,
                    'ball_num':ball_num,
                    'batting_team_won': batting_team_won
                }
                all_balls_records.append(ball_record) # Appending to the correct list
      except Exception as e:
          print(f"Error loading or processing file {file}: {e}")

  if not all_balls_records:
      print("Warning: No ball-by-ball data extracted. Returning empty DataFrame with expected columns.")
      return pd.DataFrame(columns=[
          'runs_last_6_overs', 'batting_team', 'innings',
          'bowling_team', 'cum_runs', 'balls_faced', 'cum_wickets',
          'over_num', 'ball_num', 'batting_team_won'
      ])

  balls_data_df = pd.DataFrame(all_balls_records) # Renamed to avoid confusion
  return balls_data_df

def build_match_features(df):
  if df.empty:
    print("Warning: Input DataFrame is empty, returning empty DataFrame with feature columns.")
    # Define all expected columns if input is empty, so subsequent operations don't fail on missing columns
    expected_columns = [
        'teamAplayers', 'teamBplayers', 'teamA', 'teamB', 'venue', 'date',
        'toss_winner', 'toss_decision', 'winner', 'win_rate_diff',
        'win_rate_diff_10', 'venue_win_rate_diff', 'h2h_win_rate_diff',
        'season', 'venue_exp', 'toss_won_by_A', 'toss_choice' # Add all columns that might be accessed later
    ]
    return pd.DataFrame(columns=expected_columns)

  df_sorted = df.sort_values(by=['date']).reset_index(drop=True)

  long_df = pd.concat([
    df_sorted.assign(team = df_sorted['teamA'],
                     opponent = df_sorted['teamB'],
                     winner = (df_sorted['winner'] == 1).astype(int),
                     side = 'A'),
    df_sorted.assign(team = df_sorted['teamB'],
                     opponent = df_sorted['teamA'],
                     winner = (df_sorted['winner']==0).astype(int),
                     side = 'B')],ignore_index=True)
  long_df.sort_values(['date','team']).reset_index(drop=True)
  long_df['games_played'] = 0
  long_df['wins'] = 0
  long_df['win_rate_5'] = 0.5
  long_df['win_rate_10'] = 0.5
  long_df['venue_games'] = 0
  long_df['venue_wins'] = 0
  long_df['venue_win_rate'] = 0.5
  long_df['h2h_games'] = 0
  long_df['h2h_wins'] = 0
  long_df['h2h_win_rate'] = 0.5
  long_df['win_rate_5'] = long_df.groupby('team')['winner'].rolling(5,min_periods=1).mean().shift(1).reset_index(level=0,drop=True)
  long_df['win_rate_10'] = long_df.groupby('team')['winner'].rolling(10,min_periods = 1).mean().shift(1).reset_index(level=0,drop=True)
  long_df['win_rate_5'] = long_df['win_rate_5'].fillna(0.5)
  long_df['win_rate_10'] = long_df['win_rate_10'].fillna(0.5)
  long_df['venue_win_rate'] = long_df.groupby(['team','venue'])['winner'].rolling(5,min_periods=1).mean().shift(1).reset_index(level=[0,1],drop=True)
  long_df['venue_win_rate'] = long_df['venue_win_rate'].fillna(0.5)
  long_df['h2h_games'] = long_df.groupby(['team','opponent']).cumcount()
  long_df['h2h_wins'] = (long_df.groupby(['team','opponent'])['winner'].cumsum().shift(1).fillna(0))
  long_df['h2h_win_rate'] = (long_df['h2h_wins']/long_df['h2h_games']).fillna(0.5)
  long_df.loc[long_df['h2h_games'] == 0, 'h2h_win_rate'] = 0.5
  long_df['venue_games'] = long_df.groupby(['team','venue']).cumcount()
  A = long_df[long_df['side'] == 'A'].copy()
  B = long_df[long_df['side'] == 'B'].copy()
  match_features = A.merge(B,on = ['date','venue'],suffixes=('_A','_B'))
  match_features['win_rate_diff'] = (match_features['win_rate_5_A'] - match_features['win_rate_5_B'])
  match_features['venue_win_rate_diff']= (match_features['venue_win_rate_A'] - match_features['venue_win_rate_B'])
  match_features['h2h_win_rate_diff'] = (match_features['h2h_win_rate_A'] - match_features['h2h_win_rate_B'])
  match_features['win_rate_diff_10'] = (match_features['win_rate_10_A'] - match_features['win_rate_10_B'])
  match_features['date'] = pd.to_datetime(match_features['date'])
  match_features.loc[match_features['date'].dt.year == 2023,'season'] = 1
  match_features.loc[match_features['date'].dt.year == 2024,'season'] = 2
  match_features.loc[match_features['date'].dt.year == 2025,'season'] = 3
  match_features.loc[match_features['date'].dt.year == 2026,'season'] = 4
  match_features['venue_exp'] = (match_features['venue_games_A']-match_features['venue_games_B'])
  match_features['toss_won_by_A'] = (match_features['toss_winner_A'] == match_features['team_A']).astype(int)
  match_features['toss_choice'] = (match_features['toss_decision_A']=='bat').astype(int)
  return match_features

import numpy as np
def live_features_add(df):
  balls_df = df.sort_values(['innings','over_num','ball_num']).reset_index(drop=True)
  balls_df['current_rr'] = (balls_df['cum_runs'] / (balls_df['balls_faced'].replace(0, np.nan) / 6)).fillna(0)
  balls_df['balls_remaining'] = 120 - balls_df['balls_faced']
  balls_df['overs_remaining'] = balls_df['balls_remaining'] / 6
  balls_df['wickets_left'] = 10 - balls_df['cum_wickets']

  # Initialize columns to avoid potential SettingWithCopyWarning and ensure they exist
  balls_df['target'] = 0
  balls_df['runs_needed'] = 0
  balls_df['required_rr'] = 0.0
  balls_df['rr_diff'] = 0.0

  balls_df['resources_remaining'] = ((balls_df['balls_remaining'] / 120) * (balls_df['wickets_left'] / 10)).fillna(0)




  # Use 'match_number' for groupby instead of 'match_id'


  # Use 'over_num' for powerplay/death/middle overs calculations instead of 'over'
  balls_df['is_powerplay'] = (balls_df['over_num'] < 6).astype(int)
  balls_df['is_death_overs'] = (balls_df['over_num'] >= 16).astype(int)
  balls_df['is_middle_overs'] = ((balls_df['over_num'] >= 6) & (balls_df['over_num'] < 16)).astype(int)

  return balls_df

from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from xgboost import XGBClassifier
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score
import pandas as pd
import numpy as np


from sklearn.model_selection import GridSearchCV
import numpy as np

###Pre match prediction

def train_prematch_model(df):
    split_idx = int(len(df) * 0.6)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    feature_cols = [
        'win_rate_diff','win_rate_diff_10', 'venue_win_rate_diff',
        'h2h_win_rate_diff', 'venue_exp', 'toss_won_by_A', 'toss_choice'
    ]
    X_train = train_df[feature_cols]
    X_test = test_df[feature_cols]
    y_train = train_df['winner_A']
    y_test = test_df['winner_AA']
    classifiers = {'Logistic_Regression': Pipeline(
            [('scaler', StandardScaler()),
            ('lr', LogisticRegression(random_state=42, max_iter=1000))]
        ),'RandomForest':RandomForestClassifier(random_state=42,class_weight='balanced'),'XGBoost':XGBClassifier(eval_metric='logloss',use_label_encoder=False)}
    param_grids = {
        'Logistic_Regression': {
            'lr__C': [0.01, 0.1, 1],
            'lr__penalty': ['l2']
        },
        'RandomForest': {
            'n_estimators': [50,100],
            'max_depth': [2,3,4,5],
            'min_samples_split': [5, 10]
        },
        'XGBoost': {
            'n_estimators': [100],
            'learning_rate': [0.05, 0.1],
            'max_depth': [2, 3],
            'subsample': [0.8],
            'colsample_bytree': [0.8]
        }
    }
    results = []
    from sklearn.model_selection import TimeSeriesSplit

    tscv = TimeSeriesSplit(n_splits=3)

    for key,model in classifiers.items():
      print(f"Training {key}...")
      clf = GridSearchCV(model,param_grids[key],cv=tscv,scoring='accuracy',n_jobs=-1,verbose=0)
      clf.fit(X_train,y_train)
      y_pred_train = clf.predict(X_train)
      y_pred_test = clf.predict(X_test)
      train_acc = accuracy_score(y_train, y_pred_train)
      test_acc = accuracy_score(y_test, y_pred_test)
      test_proba = clf.predict_proba(X_test)[:, 1]
      test_auc = roc_auc_score(y_test, test_proba)
      results.append({
            'Model': key,
            'Best_Params': clf.best_params_,
            'CV_Score': clf.best_score_,
            'Train_Accuracy': train_acc,
            'Test_Accuracy': test_acc,
            'clf':clf,
            'test_auc':test_auc
        })
      print(f"  Best CV Score: {clf.best_score_:.4f}")
      print(f"  Train Accuracy: {train_acc:.4f}")
      print(f"  Test Accuracy: {test_acc:.4f}")

    results_df = pd.DataFrame(results)
    best_model_result = max(results, key=lambda x: x['test_auc'])



    return {
        'model': best_model_result['clf'],
        'features': feature_cols,
        'metrics': {k: v for k, v in best_model_result.items() if k != 'clf'}
    }

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import log_loss

### During match prediction
import pickle # Added missing import for pickle
from sklearn.metrics import log_loss, roc_auc_score # Added missing import for roc_auc_score

def train_live_model(df):
    feature_ball_by_ball = ['innings',
    'cum_runs',
    'cum_wickets',
    'wickets_left',
    'balls_faced',
    'balls_remaining',
    'overs_remaining',
    'current_rr',
    'required_rr',
    'rr_diff',
    'runs_last_6_overs',
    'is_powerplay',
    'is_middle_overs',
    'is_death_overs',
    'target',
    'runs_needed']

    # Ensure df is used, not a global 'balls_df'
    X = df[feature_ball_by_ball].fillna(0)
    y = df['batting_team_won']



    models = {'GradientBoosting': GradientBoostingClassifier(loss = 'log_loss',n_estimators=300,learning_rate=0.03,max_depth=5,min_samples_split=20,subsample=0.8,random_state=42),
              'XGBoost':XGBClassifier(n_estimators=300,learning_rate=0.05,max_depth=5,subsample=0.8,colsample_bytree=0.8,eval_metric="logloss",random_state=42,n_jobs=-1),
              'RandomForest':RandomForestClassifier(n_estimators=300,max_depth=12,min_samples_split=50,class_weight='balanced',random_state=42,n_jobs=-1)}
    tscv = TimeSeriesSplit(n_splits=5)
    results = []
    for name,model in models.items():
      fold_logloss = []
      auc_scores = []
      scaler = StandardScaler()
      for fold, (train_idx,val_idx) in enumerate(tscv.split(X),1):
        X_train,X_val = X.iloc[train_idx],X.iloc[val_idx]
        y_train,y_val = y.iloc[train_idx],y.iloc[val_idx]
        if name != 'XGBoost':
          X_train = scaler.fit_transform(X_train)
          X_val = scaler.transform(X_val)
        model.fit(X_train,y_train)
        y_pred_proba = model.predict_proba(X_val)[:,1]
        logloss = log_loss(y_val,y_pred_proba)
        fold_logloss.append(logloss)
        auc_scores.append(roc_auc_score(y_val,y_pred_proba))
      mean_ll = np.mean(fold_logloss)
      mean_auc = np.mean(auc_scores)
      results.append({
            "model_name": name,
            "model": model,
            "mean_logloss": mean_ll,
            'mean_auc':mean_auc
        })

    # Corrected min function call
    best = min(results, key=lambda x: x['mean_logloss'])
    if best['model_name'] != 'XGBoost':
      X = scaler.fit_transform(X)
    best['model'].fit(X,y)

    return {
        'model': best['model'],
        'name': best['model_name'],
        'features': feature_ball_by_ball,
        'best_name': best['model_name'],
        'metrics': {'logloss': best['mean_logloss']}
    }