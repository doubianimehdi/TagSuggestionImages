import argparse
import json
import os
from pathlib import Path

import pandas as pd
import yaml
from tensorflow.keras.callbacks import ModelCheckpoint, ReduceLROnPlateau, EarlyStopping

from models import get_model
from training_utilities import (
    df_to_list_samples,
    batch_generator,
    label_mapping_from_df,
)


def train_from_csv(csv_train, csv_val, csv_labels, training_config_path):
    with open(training_config_path, "r") as f:
        training_config = yaml.load(f, yaml.SafeLoader)

    train = pd.read_csv(
        Path(training_config["data_path"]) / csv_train, usecols=["ImageID", "LabelName"]
    )

    train = train[train["ImageID"].str.startswith("c")]

    val = pd.read_csv(
        Path(training_config["data_path"]) / csv_val, usecols=["ImageID", "LabelName"]
    )

    label_df = pd.read_csv(Path(training_config["data_path"]) / csv_labels)

    label_to_int_mapping, display_labels_to_int_mapping, W = label_mapping_from_df(
        label_df
    )

    train_samples = df_to_list_samples(
        train, label_df=label_df, fold="train_c_small"
    )  # train
    val_samples = df_to_list_samples(val, label_df=label_df, fold="validation_small")

    train_samples = [
        x
        for x in train_samples
        if os.path.isfile(training_config["data_path"] + x.path)
    ]
    val_samples = [
        x for x in val_samples if os.path.isfile(training_config["data_path"] + x.path)
    ]

    model, _, _ = get_model(
        vocab_size=max(label_to_int_mapping.values()) + 1,
        W=W,
        trainable=training_config["train_embeddings"],
    )
    print("train_samples", len(train_samples))
    print("val_samples", len(val_samples))

    train_gen = batch_generator(
        train_samples,
        resize_size=training_config["resize_shape"],
        augment=training_config["use_augmentation"],
        base_path=training_config["data_path"],
    )
    val_gen = batch_generator(
        val_samples,
        resize_size=training_config["resize_shape"],
        base_path=training_config["data_path"],
    )

    checkpoint = ModelCheckpoint(
        training_config["model_path"],
        monitor="val_loss",
        verbose=1,
        save_best_only=True,
        mode="min",
    )
    reduce = ReduceLROnPlateau(monitor="val_loss", mode="min", patience=50, min_lr=1e-7)
    early = EarlyStopping(monitor="val_loss", mode="min", patience=300)

    with open(training_config["label_display_to_int"], "w") as f:
        json.dump(display_labels_to_int_mapping, f, indent=4)

    try:
        model.load_weights(training_config["model_path"])
    except:
        print("No model to load")

    model.fit_generator(
        train_gen,
        steps_per_epoch=300,  # len(train_samples) // training_config["batch_size"]
        validation_data=val_gen,
        validation_steps=100,  # len(val_samples) // training_config["batch_size"]
        epochs=training_config["epochs"],
        callbacks=[checkpoint, reduce, early],
        use_multiprocessing=True,
        workers=8,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv_train",
        help="csv_train",
        default="c3-train-annotations-human-imagelabels.csv",  #  oidv6-train
    )
    parser.add_argument(
        "--csv_val",
        help="csv_val",
        default="validation-annotations-human-imagelabels.csv",
    )
    parser.add_argument(
        "--csv_labels", help="csv_labels", default="oidv6-class-descriptions.csv"
    )
    parser.add_argument(
        "--training_config_path",
        help="training_config_path",
        default="../example/training_config.yaml",
    )
    args = parser.parse_args()

    csv_train = args.csv_train
    csv_val = args.csv_val
    csv_labels = args.csv_labels

    training_config_path = args.training_config_path

    train_from_csv(
        csv_train=csv_train,
        csv_val=csv_val,
        csv_labels=csv_labels,
        training_config_path=training_config_path,
    )
