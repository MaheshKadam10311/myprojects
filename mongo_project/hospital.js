const { MongoClient } = require('mongodb');
const url = 'mongodb+srv://maheshkadam10311:<password>@cluster0.zjio2g1.mongodb.net/'; // MongoDB connection string
const dbName = 'hospitalDB'; // Name of your database
const client = new MongoClient(url);

async function main() {
  try {
    // Connect to MongoDB
    await client.connect();
    console.log('Connected to the database');

    const db = client.db(dbName);
    const patientsCollection = db.collection('patients');
    const doctorsCollection = db.collection('doctors');

    // Example: Inserting a patient
    await patientsCollection.insertOne({
      name: 'John Doe',
      age: 35,
      gender: 'Male',
      disease: 'Fever'
    });
    console.log('Patient inserted successfully');

    // Example: Inserting a doctor
    await doctorsCollection.insertOne({
      name: 'Dr. Smith',
      specialization: 'Cardiologist',
      experience: 10
    });
    console.log('Doctor inserted successfully');

    // Example: Finding all patients
    const allPatients = await patientsCollection.find().toArray();
    console.log('All patients:', allPatients);

    // Example: Finding all doctors
    const allDoctors = await doctorsCollection.find().toArray();
    console.log('All doctors:', allDoctors);
  } catch (err) {
    console.error(err);
  } finally {
    // Close the connection to MongoDB
    await client.close();
    console.log('Disconnected from the database');
  }
}

main();