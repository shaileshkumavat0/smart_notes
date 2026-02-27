from flask import Blueprint, render_template, request, redirect, session, url_for, jsonify, flash
from bson.objectid import ObjectId
from .database import notes_collection
from .auth import register_user, login_user
import datetime

main = Blueprint("main", __name__)

@main.route("/")
def home():
    if "user" in session:
        return redirect(url_for("main.notes"))
    return redirect(url_for("main.login"))

@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if register_user(username, password):
            flash("Account created successfully. Please log in 🎉", "success")
            return redirect(url_for("main.login"))
        else:
            flash("User already exists. Try a different username.", "danger")
            return redirect(url_for("main.register"))

    return render_template("register.html")

@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = login_user(username, password)
        if user:
            session["user"] = username
            return redirect(url_for("main.notes"))
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("main.login"))

    return render_template("login.html")

@main.route("/notes", methods=["GET", "POST"])
def notes():
    if "user" not in session:
        return redirect(url_for("main.login"))

    search_query = request.args.get("search", "")
    active_tag = request.args.get("tag", "all")
    sort = request.args.get("sort", "new")
    view = request.args.get("view", "active")  # active | archived | all
    
    if request.method == "POST":
        content = request.form.get("content", "")
        tag = request.form.get("tag", "general")
        
        if content.strip():
            notes_collection.insert_one({
                "username": session["user"],
                "content": content,
                "tag": tag,
                "pinned": False,
                "archived": False,
                "created_at": datetime.datetime.utcnow(),
                "updated_at": datetime.datetime.utcnow()
            })
            flash("Note added successfully ✅", "success")
    
    # Build query
    query = {"username": session["user"]}
    if search_query:
        query["content"] = {"$regex": search_query, "$options": "i"}
    if active_tag != "all":
        query["tag"] = active_tag

    if view == "active":
        query["archived"] = {"$ne": True}
    elif view == "archived":
        query["archived"] = True
    
    # Sort options
    if sort == "old":
        sort_order = [("pinned", -1), ("created_at", 1)]
    elif sort == "az":
        sort_order = [("pinned", -1), ("content", 1)]
    else:  # "new"
        sort_order = [("pinned", -1), ("created_at", -1)]

    user_notes = list(notes_collection.find(query).sort(sort_order))

    # Simple stats & tag summary for UI
    base_user_query = {"username": session["user"]}
    total_notes = notes_collection.count_documents(base_user_query)
    pinned_count = notes_collection.count_documents({**base_user_query, "pinned": True, "archived": {"$ne": True}})
    active_count = notes_collection.count_documents({**base_user_query, "archived": {"$ne": True}})
    archived_count = notes_collection.count_documents({**base_user_query, "archived": True})

    # Tag counts (only active notes for a clean overview)
    tags_summary = {
        "general": notes_collection.count_documents({**base_user_query, "tag": "general", "archived": {"$ne": True}}),
        "work": notes_collection.count_documents({**base_user_query, "tag": "work", "archived": {"$ne": True}}),
        "personal": notes_collection.count_documents({**base_user_query, "tag": "personal", "archived": {"$ne": True}}),
        "ideas": notes_collection.count_documents({**base_user_query, "tag": "ideas", "archived": {"$ne": True}}),
        "important": notes_collection.count_documents({**base_user_query, "tag": "important", "archived": {"$ne": True}}),
    }
    
    return render_template(
        "notes.html",
        notes=user_notes,
        search_query=search_query,
        active_tag=active_tag,
        sort=sort,
        view=view,
        total_notes=total_notes,
        pinned_count=pinned_count,
        active_count=active_count,
        archived_count=archived_count,
        tags_summary=tags_summary,
        username=session.get("user")
    )

@main.route("/edit/<note_id>", methods=["GET", "POST"])
def edit_note(note_id):
    if "user" not in session:
        return redirect(url_for("main.login"))
    
    if request.method == "POST":
        content = request.form.get("content", "")
        tag = request.form.get("tag", "general")
        
        notes_collection.update_one(
            {"_id": ObjectId(note_id), "username": session["user"]},
            {"$set": {
                "content": content,
                "tag": tag,
                "updated_at": datetime.datetime.utcnow()
            }}
        )
        flash("Note updated ✏️", "success")
        return redirect(url_for("main.notes"))
    
    note = notes_collection.find_one({"_id": ObjectId(note_id), "username": session["user"]})
    if note:
        return render_template("edit_note.html", note=note)
    return redirect(url_for("main.notes"))

@main.route("/pin/<note_id>")
def pin_note(note_id):
    if "user" not in session:
        return redirect(url_for("main.login"))
    
    note = notes_collection.find_one({"_id": ObjectId(note_id), "username": session["user"]})
    if note:
        new_pinned_status = not note.get("pinned", False)
        notes_collection.update_one(
            {"_id": ObjectId(note_id)},
            {"$set": {"pinned": new_pinned_status}}
        )
        flash("Note pinned ✅" if new_pinned_status else "Note unpinned.", "info")
    return redirect(url_for("main.notes"))

@main.route("/archive/<note_id>")
def archive_note(note_id):
    if "user" not in session:
        return redirect(url_for("main.login"))

    note = notes_collection.find_one({"_id": ObjectId(note_id), "username": session["user"]})
    if note:
        new_archived_status = not note.get("archived", False)
        notes_collection.update_one(
            {"_id": ObjectId(note_id)},
            {"$set": {"archived": new_archived_status}}
        )
        flash(
            "Note moved to archive 📦" if new_archived_status else "Note restored from archive.",
            "info"
        )
    return redirect(url_for("main.notes"))

@main.route("/delete/<note_id>")
def delete_note(note_id):
    notes_collection.delete_one({"_id": ObjectId(note_id), "username": session["user"]})
    flash("Note deleted 🗑️", "warning")
    return redirect(url_for("main.notes"))

@main.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("main.login"))

@main.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("main.login"))

    username = session["user"]
    base_query = {"username": username}

    # High level stats
    total_notes = notes_collection.count_documents(base_query)
    active_notes = notes_collection.count_documents({**base_query, "archived": {"$ne": True}})
    archived_notes = notes_collection.count_documents({**base_query, "archived": True})
    pinned_notes = notes_collection.count_documents({**base_query, "pinned": True, "archived": {"$ne": True}})

    # Tag distribution (active notes only)
    tag_keys = ["general", "work", "personal", "ideas", "important"]
    tag_counts = {
        tag: notes_collection.count_documents({**base_query, "tag": tag, "archived": {"$ne": True}})
        for tag in tag_keys
    }

    # Favourite tag and a small insight
    favourite_tag = None
    if total_notes > 0:
        favourite_tag = max(tag_counts, key=tag_counts.get)

    # Activity over last 7 days
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=6)

    pipeline = [
        {
            "$match": {
                **base_query,
                "created_at": {
                    "$gte": datetime.datetime.combine(start_date, datetime.time.min)
                },
            }
        },
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    agg_results = list(notes_collection.aggregate(pipeline))
    grouped_counts = {doc["_id"]: doc["count"] for doc in agg_results}

    notes_by_day_labels = []
    notes_by_day_counts = []

    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        key = day.strftime("%Y-%m-%d")
        notes_by_day_labels.append(day.strftime("%d %b"))
        notes_by_day_counts.append(grouped_counts.get(key, 0))

    # Some "smart" examples to surface
    last_note = notes_collection.find_one(
        base_query, sort=[("updated_at", -1)]
    )
    longest_note = notes_collection.find_one(
        base_query,
        sort=[("content_length", -1), ("updated_at", -1)],
    )

    # Backfill content_length lazily if missing
    if not longest_note:
        # compute length on the fly
        pipeline_longest = [
            {"$match": base_query},
            {
                "$project": {
                    "content": 1,
                    "tag": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "length": {"$strLenCP": "$content"},
                }
            },
            {"$sort": {"length": -1}},
            {"$limit": 1},
        ]
        longest_list = list(notes_collection.aggregate(pipeline_longest))
        longest_note = longest_list[0] if longest_list else None

    # Prepare tag chart data
    tag_label_map = {
        "general": "General",
        "work": "Work",
        "personal": "Personal",
        "ideas": "Ideas",
        "important": "Important",
    }
    tag_chart_labels = [tag_label_map[t] for t in tag_keys]
    tag_chart_counts = [tag_counts[t] for t in tag_keys]

    return render_template(
        "dashboard.html",
        username=username,
        total_notes=total_notes,
        active_notes=active_notes,
        archived_notes=archived_notes,
        pinned_notes=pinned_notes,
        favourite_tag=favourite_tag,
        tag_counts=tag_counts,
        tag_chart_labels=tag_chart_labels,
        tag_chart_counts=tag_chart_counts,
        notes_by_day_labels=notes_by_day_labels,
        notes_by_day_counts=notes_by_day_counts,
        last_note=last_note,
        longest_note=longest_note,
    )

# API endpoint for real-time search
@main.route("/api/search")
def search_notes():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    query = request.args.get("q", "")
    notes = list(notes_collection.find({
        "username": session["user"],
        "content": {"$regex": query, "$options": "i"},
        "archived": {"$ne": True}
    }).sort([("pinned", -1), ("created_at", -1)]))
    
    results = []
    for note in notes:
        results.append({
            "_id": str(note["_id"]),
            "content": note["content"],
            "tag": note.get("tag", "general"),
            "pinned": note.get("pinned", False),
            "created_at": note.get("created_at").isoformat() if note.get("created_at") else None,
            "updated_at": note.get("updated_at").isoformat() if note.get("updated_at") else None
        })
    
    return jsonify(results)
